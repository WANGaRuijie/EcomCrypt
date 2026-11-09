"""Two-stage LLM screening (title triage, then abstract decision) with bounded spend.

* Requests run concurrently (default 8 in flight); budget reservations and all
  database writes happen on the main thread.
* Each work is screened at most once per (stage, rubric version, input). A later
  abstract recovery re-opens only works previously parked as needs_fulltext.
* Prices are upper bounds from data/pipeline_config_v1.json; every request is
  reserved before it is sent and settled from the reported token usage. A failed
  request keeps its full reservation (unknown billing is never assumed free).
"""
import hashlib
import json
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import rubric
from store import BudgetExhausted

ENDPOINT = 'https://api.deepseek.com/chat/completions'


class LLMError(RuntimeError):
    pass


class DeepSeek:
    def __init__(self, key, model, *, price_in_per_m, price_out_per_m, timeout=150):
        if not key:
            raise LLMError('DEEPSEEK_API_KEY is missing (use scripts/monthly.ps1 on Windows).')
        self.key, self.model, self.timeout = key, model, timeout
        self.price_in = price_in_per_m * 1000      # nanodollars per token
        self.price_out = price_out_per_m * 1000

    def estimate(self, system, user, max_tokens):
        tokens_in = (len(system) + len(user)) // 3 + 50
        return int(tokens_in * self.price_in + max_tokens * self.price_out)

    def cost(self, usage):
        prompt, completion = usage.get('prompt_tokens'), usage.get('completion_tokens')
        if type(prompt) is not int or type(completion) is not int or prompt < 0 or completion < 0:
            raise LLMError('unexpected token usage')
        return int(prompt * self.price_in + completion * self.price_out)

    def complete(self, system, user, max_tokens):
        payload = {'model': self.model, 'temperature': 0, 'max_tokens': max_tokens,
                   'response_format': {'type': 'json_object'}, 'thinking': {'type': 'disabled'},
                   'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}
        request = Request(ENDPOINT, data=json.dumps(payload, ensure_ascii=False).encode(), headers={
            'Authorization': f'Bearer {self.key}', 'Content-Type': 'application/json'})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.load(response)
        except HTTPError as error:
            raise LLMError(f'DeepSeek HTTP {error.code}') from None
        except (URLError, OSError, ValueError):
            raise LLMError('DeepSeek network/response error') from None
        choice = (result.get('choices') or [{}])[0]
        return (choice.get('message') or {}).get('content') or '', choice.get('finish_reason'), result.get('usage') or {}


def _hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def _paper(store, work, stage):
    item = {'title': work['title'], 'venue': work.get('venue') or '', 'year': work.get('year')}
    if stage == 'abstract':
        item['abstract'] = (work.get('abstract') or '')[:2500]
        if work.get('tldr'):
            item['machine_summary'] = work['tldr']
    return item


def needs_screen(store, work, stage, version, retry_invalid=False):
    item = _paper(store, work, stage)
    result, input_hash = store.screen(work['key'], stage, version)
    if result is None:
        return True, item
    if retry_invalid and stage == 'abstract' and 'not_verbatim' in str(result.get('validation') or ''):
        return True, item
    if stage == 'abstract' and result.get('decision') == 'needs_fulltext' and input_hash != _hash(item):
        return True, item
    return False, item


def run_stage(store, works, *, stage, llm, spend, batch_size, concurrency=8, log=print, rubric_path=None, retry_invalid=False):
    rubric_path = str(rubric_path or rubric.RUBRIC)
    version = rubric.version(rubric_path)
    system = rubric.title_prompt(rubric_path) if stage == 'title' else rubric.abstract_prompt(rubric_path)
    max_tokens = 3200 if stage == 'title' else 4200
    todo = []
    for work in works:
        due, item = needs_screen(store, work, stage, version, retry_invalid)
        if due:
            todo.append((work, item))
    batches = [todo[i:i + batch_size] for i in range(0, len(todo), batch_size)]
    stats = {'stage': stage, 'works': len(todo), 'requests': 0, 'failed_requests': 0, 'decisions': {}, 'budget_stopped': False}
    if not batches:
        log(f'screen[{stage}]: nothing to do')
        return stats

    def submit(pool, batch):
        papers = [{'id': f'p{i}', **item} for i, (_, item) in enumerate(batch)]
        user = json.dumps({'papers': papers}, ensure_ascii=False)
        request_id = spend.reserve(llm.estimate(system, user, max_tokens))
        return pool.submit(llm.complete, system, user, max_tokens), request_id, batch, papers

    pending, queue = {}, list(batches)
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        while queue or pending:
            while queue and len(pending) < concurrency and not stats['budget_stopped']:
                try:
                    future, request_id, batch, papers = submit(pool, queue[0])
                except BudgetExhausted as error:
                    log(str(error))
                    stats['budget_stopped'] = True
                    break
                queue.pop(0)
                pending[future] = (request_id, batch, papers)
            if not pending:
                break
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                request_id, batch, papers = pending.pop(future)
                stats['requests'] += 1
                try:
                    content, finish, usage = future.result()
                    spend.settle(request_id, llm.cost(usage))
                except LLMError as error:
                    stats['failed_requests'] += 1
                    log(f'screen[{stage}]: request failed ({error}); {len(batch)} works stay unscreened')
                    continue
                if finish != 'stop' and len(batch) > 1:
                    half = len(batch) // 2
                    queue[:0] = [batch[:half], batch[half:]]
                    continue
                try:
                    rows = json.loads(content).get('results')
                except (ValueError, AttributeError):
                    rows = None
                by_id = {r.get('id'): r for r in rows if isinstance(r, dict)} if isinstance(rows, list) else {}
                with store.tx():
                    for paper, (work, item) in zip(papers, batch):
                        row = by_id.get(paper['id'])
                        if stage == 'title':
                            keep = not (isinstance(row, dict) and row.get('keep') is False)
                            result = {'keep': keep, 'code': (row or {}).get('code') if not keep else None}
                            if row is None:
                                result['validation'] = 'missing_row_kept_for_recall'
                            status = 'title_keep' if keep else 'title_drop'
                            reason = result['code']
                        else:
                            result = rubric.validate_abstract_row(row or {}, {'id': paper['id'], **item}, rubric_path)
                            result.pop('id', None)
                            status = {'include': 'screen_include', 'exclude': 'screen_exclude',
                                      'needs_fulltext': 'needs_fulltext'}[result['decision']]
                            reason = result.get('code') or result.get('reason')
                        store.save_screen(work['key'], stage, version, _hash(item), llm.model, result)
                        store.set_status(work['key'], status, reason)
                        stats['decisions'][status] = stats['decisions'].get(status, 0) + 1
            if stats['requests'] % 25 == 0 and stats['requests']:
                log(f"screen[{stage}]: {stats['requests']} requests, spend ${spend.used / 1e9:.4f}")
    log(f"screen[{stage}]: {stats['works']} works, {stats['requests']} requests, decisions={stats['decisions']}, "
        f"run spend upper ${spend.used / 1e9:.4f}" + (' (budget reached; remainder stays queued)' if stats['budget_stopped'] else ''))
    return stats
