"""EcomCrypt monthly pipeline: harvest -> dedupe -> prefilter -> triage -> enrich -> screen -> promote -> report.

Typical month (Windows, keys loaded by the wrapper):

    & .\\scripts\\monthly.ps1 run                 # everything, dry-run promotion
    & .\\scripts\\monthly.ps1 run --apply         # same, and write accepted works to the ledger
    & .\\scripts\\monthly.ps1 dblp --download     # when a new monthly DBLP release is out

One-time setup on an existing project: ``init`` (directory + legacy caches), then ``dblp``.
All state lives in .cache/pipeline/store.sqlite; ``export`` mirrors every screening
decision to data/screening_ledger_v2.jsonl (and ``restore`` rebuilds from it), so the
"never screen the same work twice" memory survives a lost cache.
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import rubric  # noqa: E402
import venue_policy  # noqa: E402
from directory import read_json, write_json  # noqa: E402
from metadata import normalize_title  # noqa: E402
from store import TERMINAL, Spend, Store  # noqa: E402

CONFIG = ROOT / 'data/pipeline_config_v1.json'
EXPORT = ROOT / 'data/screening_ledger_v2.jsonl'
OUT = ROOT / '.out/monthly'
OPEN = {'new', 'prefilter_pass', 'prefilter_drop', 'venue_unknown', 'denied_venue', 'title_keep', 'title_drop'}
SCREENED = {'screen_include', 'screen_exclude', 'needs_fulltext'}


def log(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


def load_config():
    return read_json(CONFIG)


def current_directory():
    from build import EVIDENCE, LEDGER, SEEDS, project
    return project(read_json(SEEDS), read_json(EVIDENCE), read_json(LEDGER) if LEDGER.exists() else None)


def directory_index(directory, min_papers=2):
    works, authors, names = set(), set(), Counter()
    for paper in directory['papers']:
        for edition in [paper, *paper.get('versions', []), *paper.get('publications', [])]:
            if (oa := (edition.get('source_ids') or {}).get('openalex')):
                works.add(oa)
        for credit in paper.get('author_credits') or []:
            names[normalize_title(credit['name'])] += 1
    for researcher in directory['researchers']:
        if (oa := researcher.get('identity_ids', {}).get('openalex')):
            authors.add(oa)
    return {'openalex_works': sorted(works), 'openalex_authors': sorted(authors),
            'known_author_names': {n for n, c in names.items() if c >= min_papers and n}}


# --- sync / refresh ---------------------------------------------------------

def sync_directory(store, directory=None):
    directory = directory or current_directory()
    for paper in directory['papers']:
        for edition in [paper, *paper.get('versions', []), *paper.get('publications', [])]:
            store.add({**edition, 'source': 'directory', 'source_id': f"{paper['id']}#{edition.get('doi') or edition.get('title')}"},
                      origin='directory', status='in_directory', directory_id=paper['id'])
    return directory


def venue_view(editions):
    from promote import best_edition
    edition = best_edition(editions)
    if edition is None:
        return {'decision': 'unknown', 'reason': 'no usable edition'}, None
    verdict = venue_policy.classify(edition)
    if verdict['decision'] == 'preprint':
        verdict['group'] = 'Preprint'
    return verdict, edition


def prefilter_group(group, venue_id, venue):
    """The venue group that widens the keyword gate; general AI venues widen nothing."""
    if venue_id in rubric.load()['prefilter']['venue_rules'].get('no_widening_venue_ids', []):
        return None
    if group == 'Preprint' and 'eprint' in (venue or '').lower():
        return 'Security & Crypto'
    return group


def refresh(store, *, keys=None):
    """Recompute venue/prefilter status for every non-terminal work (cheap; no network)."""
    version = rubric.version()
    rows = [store.work(k) for k in keys] if keys else store.works()
    changed = Counter()
    with store.tx():
        for work in rows:
            if not work or work['status'] in TERMINAL or work['status'].startswith(('review_', 'held_')):
                continue
            verdict, edition = venue_view(store.editions(work['key']))
            fields = {'venue_decision': verdict['decision'], 'venue_group': verdict.get('group'), 'venue_id': verdict.get('venue_id')}
            if edition:
                fields.update(venue=edition.get('venue') or work['venue'], year=edition.get('year') or work['year'])
            abstract_screen, _ = store.screen(work['key'], 'abstract', version)
            title_screen, _ = store.screen(work['key'], 'title', version)
            if verdict['decision'] == 'deny':
                status, reason = 'denied_venue', verdict['reason']
            elif verdict['decision'] == 'unknown':
                status, reason = 'venue_unknown', f"unregistered venue: {fields.get('venue') or '-'}"
            elif abstract_screen:
                status = {'include': 'screen_include', 'exclude': 'screen_exclude', 'needs_fulltext': 'needs_fulltext'}[abstract_screen['decision']]
                reason = abstract_screen.get('code') or abstract_screen.get('reason')
            elif title_screen:
                status = 'title_keep' if title_screen['keep'] else 'title_drop'
                reason = title_screen.get('code')
            else:
                gate = prefilter_group(fields['venue_group'], fields.get('venue_id'), fields.get('venue') or work['venue'])
                passed, reason, signals = rubric.prefilter(work['title'], work.get('abstract') or '', gate)
                if not passed and reason != 'prefilter_non_research_item':
                    if work.get('curated'):
                        passed, reason = True, 'prefilter_bypass_curated_lane'
                    elif _known_author(store, work['key']) and signals:
                        passed, reason = True, 'prefilter_known_author'
                status = 'prefilter_pass' if passed else 'prefilter_drop'
                fields['signals'] = signals
            if status != work['status']:
                changed[status] += 1
            store.set_status(work['key'], status, reason, **fields)
    log('refresh: ' + (', '.join(f'{k}+{v}' for k, v in changed.items()) or 'no changes'))
    return changed


_KNOWN = {}


def _known_author(store, key):
    names = _KNOWN.get('names')
    if names is None:
        return False
    for edition in store.editions(key):
        if any(normalize_title(a.get('name') if isinstance(a, dict) else a) in names for a in edition.get('authors') or []):
            return True
    return False


# --- ingestion --------------------------------------------------------------

def cmd_init(args, store, config):
    directory = sync_directory(store)
    log(f"init: directory synced ({len(directory['papers'])} works)")
    counts = import_legacy(store)
    log(f'init: legacy import {counts}')
    index = directory_index(directory, config['dblp']['known_author_min_papers'])
    _KNOWN['names'] = index['known_author_names']
    if counts.get('graphs'):
        # The legacy author/citation sweeps already covered these IDs; continue from initial_since.
        with store.tx():
            for prefix, ids in (('cites', index['openalex_works']), ('author', index['openalex_authors'])):
                for identifier in ids:
                    if not store.get_mark(f'{prefix}:{identifier}'):
                        store.set_mark(f'{prefix}:{identifier}', config['feeds']['initial_since'])
    refresh(store)


def import_legacy(store):
    """Fold the ChatGPT-era caches (evidence queue + discovery graphs) into the store, once."""
    if store.get_mark('legacy_import'):
        return {'skipped': 'already imported on ' + store.get_mark('legacy_import')}
    counts = Counter()
    queue = ROOT / '.out/evidence-review/queue.json'
    if queue.exists():
        for row in read_json(queue)['records']:
            raw = row.get('raw_input') or {}
            if raw.get('title'):
                _, new = store.add(raw, origin='legacy:evidence-queue', abstract=row.get('abstract'))
                counts['evidence_queue'] += 1
                counts['new_works'] += new
    paths = []
    state = ROOT / '.out/scheduled-curation/state.json'
    if state.exists():
        paths += read_json(state).get('discovery_graph_paths', [])
    manifest = ROOT / '.out/bibliography-sweep/manifest.json'
    if manifest.exists():
        paths += read_json(manifest).get('graph_paths', [])
    for raw_path in dict.fromkeys(paths):
        path = ROOT / raw_path.replace('\\', '/')
        if not path.exists():
            counts['missing_graphs'] += 1
            continue
        try:
            graph = read_json(path)
        except (OSError, ValueError):
            counts['unreadable_graphs'] += 1
            continue
        counts['graphs'] += 1
        for node in graph.get('nodes', []):
            for source in node.get('sources', []):
                if source.get('title') and source.get('source') in {'openalex', 'arxiv', 'dblp', 'crossref', 'publisher'}:
                    _, new = store.add(source, origin='legacy:graph', abstract=source.get('abstract'))
                    counts['records'] += 1
                    counts['new_works'] += new
    store.set_mark('legacy_import', date.today().isoformat())
    return dict(counts)


def cmd_dblp(args, store, config):
    import source_dblp
    if args.file:
        path = Path(args.file)
        release = args.release or path.name.removeprefix('dblp-').split('.xml')[0]
    else:
        release, path = source_dblp.download(ROOT / config['dblp']['download_dir'])
    if store.get_mark('dblp_release') == release and not args.force:
        log(f'dblp: release {release} already ingested (use --force to re-read)')
        return
    names = directory_index(current_directory(), config['dblp']['known_author_min_papers'])['known_author_names']
    _KNOWN['names'] = names

    def accept(record):
        verdict = venue_policy.classify(record)
        if verdict['decision'] == 'deny':
            return False
        group = 'Preprint' if verdict['decision'] == 'preprint' else verdict.get('group')
        passed, _, signals = rubric.prefilter(record['title'], '', group)
        if passed:
            return True
        return bool(signals) and any(normalize_title(a['name']) in names for a in record['authors'])

    stats = source_dblp.ingest(path, store, accept=accept, release=release, min_year=config['dblp']['min_year'])
    log(f'dblp {release}: {stats}')
    refresh(store)


def cmd_feeds(args, store, config):
    import source_feeds as feeds
    http = feeds.Http()
    today = date.today().isoformat()
    lookback = timedelta(days=config['feeds']['lookback_days'])
    index = directory_index(current_directory(), config['dblp']['known_author_min_papers'])
    _KNOWN['names'] = index['known_author_names']
    selected = set(args.only or ['openalex', 'arxiv', 'eprint'])
    touched = []

    def since_for(lane, initial):
        mark = store.get_mark(f'feed:{lane}')
        if not mark:
            return initial
        return (date.fromisoformat(mark) - lookback).isoformat()

    def take(records, lane):
        n = new = 0
        for record in records:
            key, is_new = store.add(record, origin=lane, abstract=record.get('abstract'))
            n += 1
            new += is_new
            if is_new:
                touched.append(key)
        return n, new

    if 'openalex' in selected:
        for lane, filter_expr in feeds.openalex_keyword_lanes(config, '{since}'):
            since = since_for(lane, config['feeds']['initial_since'])
            try:
                n, new = take(feeds.openalex_pages(http, filter_expr.replace('{since}', since),
                                                   max_pages=config['openalex']['max_pages_per_lane']), lane)
            except feeds.FeedError as error:
                log(f'{lane}: stopped ({error}); watermark kept at {store.get_mark(f"feed:{lane}")}')
                continue
            store.set_mark(f'feed:{lane}', today)
            log(f'{lane}: since {since}: {n} records, {new} new works')
        # Per-ID watermarks: a work/author added to the directory later gets its full
        # history once (citations / bibliography since dblp.min_year), then monthly deltas.
        full = f"{config['dblp']['min_year']}-01-01"
        for kind, prefix, ids in (('cites', 'cites', index['openalex_works']),
                                  ('authorships.author.id', 'author', index['openalex_authors'])):
            groups = defaultdict(list)
            for identifier in ids:
                groups[since_for(f'{prefix}:{identifier}', full)].append(identifier)
            n_total = new_total = failed = 0
            for since, members in sorted(groups.items()):
                for i in range(0, len(members), 80):
                    chunk = members[i:i + 80]
                    try:
                        n, new = take(feeds.openalex_pages(http, feeds.openalex_id_filter(config, kind, chunk, since),
                                                           max_pages=config['openalex']['max_pages_per_lane']), f'openalex:{prefix}')
                    except feeds.FeedError as error:
                        failed += len(chunk)
                        log(f'openalex:{prefix}: chunk since {since} stopped ({error}); its watermarks are kept')
                        continue
                    with store.tx():
                        for identifier in chunk:
                            store.set_mark(f'{prefix}:{identifier}', today)
                    n_total += n
                    new_total += new
            log(f'openalex:{prefix}: {len(ids)} IDs, {n_total} records, {new_total} new works' + (f', {failed} IDs failed' if failed else ''))
    if 'arxiv' in selected:
        since = since_for('arxiv', config['feeds']['initial_since'])
        try:
            n, new = take(feeds.arxiv_window(http, config['feeds']['arxiv_categories'], since, today), 'arxiv')
            store.set_mark('feed:arxiv', today)
            log(f'arxiv: since {since}: {n} records, {new} new works')
        except feeds.FeedError as error:
            log(f'arxiv: stopped ({error})')
    if 'eprint' in selected:
        since = since_for('eprint', config['feeds']['eprint_initial_since'])
        try:
            n, new = take(feeds.eprint_since(http, since), 'eprint')
            store.set_mark('feed:eprint', today)
            log(f'eprint: since {since}: {n} records, {new} new works')
        except feeds.FeedError as error:
            log(f'eprint: stopped ({error})')
    refresh(store)


# --- screening ----------------------------------------------------------------

def _llm(config):
    from screen import DeepSeek
    c = config['llm']
    return DeepSeek(os.environ.get('DEEPSEEK_API_KEY'), c['model'], price_in_per_m=c['price_in_per_m_usd'],
                    price_out_per_m=c['price_out_per_m_usd'])


def cmd_screen(args, store, config, run_id):
    from screen import run_stage
    import source_feeds as feeds
    from enrich import enrich
    c = config['llm']
    llm = _llm(config)
    spend = Spend(store, run_id, args.budget if args.budget is not None else c['budget_usd_per_run'])
    limit = args.limit
    min_year = getattr(args, 'min_year', None)
    groups = set(getattr(args, 'group', None) or [])

    def select(statuses):
        works = [w for w in store.works(statuses) if (not min_year or (w.get('year') or 0) >= min_year)
                 and (not groups or w.get('venue_group') in groups)]
        return works[:limit] if limit else works

    if args.stage in {'title', 'all'}:
        works = select(['prefilter_pass'])
        run_stage(store, works, stage='title', llm=llm, spend=spend, batch_size=c['title_batch'], concurrency=c['concurrency'], log=log)
    if args.stage in {'enrich', 'all'} or (args.stage == 'abstract' and not args.no_enrich):
        kept = select(['title_keep'])
        keys = [w['key'] for w in kept if len(w.get('abstract') or '') < 200]
        keys += [w['key'] for w in kept if w.get('venue_decision') == 'unresolved' and w['key'] not in keys]
        if keys:
            enrich(store, feeds.Http(), keys, s2_key=os.environ.get('S2_API_KEY'),
                   use_crossref=config['enrich']['crossref'], log=log)
            refresh(store, keys=keys)      # park newly resolved unknown/denied venues before paying for abstracts
    if args.stage in {'abstract', 'all'}:
        works = select(['title_keep', 'needs_fulltext'])
        if getattr(args, 'with_abstract', False):
            works = [w for w in works if len(w.get('abstract') or '') >= 200]
        run_stage(store, works, stage='abstract', llm=llm, spend=spend, batch_size=c['abstract_batch'], concurrency=c['concurrency'], log=log,
                  retry_invalid=getattr(args, 'retry_invalid', False))
    log(f'screen: run {run_id} spend upper ${spend.used / 1e9:.4f}; all pipeline runs ${spend.total_all_runs() / 1e9:.4f}')


def cmd_enrich(args, store, config):
    import source_feeds as feeds
    from enrich import enrich
    statuses = args.status or ['title_keep', 'needs_fulltext']
    keys = [w['key'] for w in store.works(statuses, limit=args.limit) if len(w.get('abstract') or '') < 200]
    enrich(store, feeds.Http(), keys, s2_key=os.environ.get('S2_API_KEY'), use_crossref=config['enrich']['crossref'], log=log)


def cmd_promote(args, store, config):
    from promote import promote
    batch = {'confidence': getattr(args, 'confidence', None), 'kind': getattr(args, 'kind', None), 'groups': set(getattr(args, 'group', None) or [])}
    outcome = promote(store, config, apply=args.apply, log=log, batch=batch)
    return outcome


def cmd_topics(args, store, config, run_id):
    from topics_llm import retag
    c = config['llm']
    retag(store, current_directory(), _llm(config), Spend(store, run_id, args.budget if args.budget is not None else c['budget_usd_per_run']),
          log=log, concurrency=c['concurrency'])


# --- reporting -------------------------------------------------------------

def build_report(store, run_id, outcome=None, started=None):
    version = rubric.version()
    counts = store.counts()
    unknown = defaultdict(list)
    for work in store.works(['venue_unknown']):
        passed, _, _ = rubric.prefilter(work['title'], work.get('abstract') or '')
        if passed or work.get('curated'):
            unknown[work.get('venue') or '(missing venue)'].append(work['title'])
    unknown_rows = sorted(({'venue': v, 'count': len(t), 'examples': t[:3]} for v, t in unknown.items()), key=lambda r: -r['count'])
    review = []
    for status in ('needs_fulltext', 'review_confidence', 'review_metadata', 'held_editorial'):
        for work in store.works([status]):
            screen, _ = store.screen(work['key'], 'abstract', version)
            review.append({'status': status, 'title': work['title'], 'year': work['year'], 'venue': work['venue'],
                           'reason': work.get('status_reason'), 'topics': (screen or {}).get('topics'),
                           'has_abstract': len(work.get('abstract') or '') >= 200,
                           'links': [a['alias'] for a in store.db.execute("SELECT alias FROM aliases WHERE key=? AND alias NOT LIKE 't:%'", (work['key'],))]})
    new_this_run = store.db.execute('SELECT origin, COUNT(*) n FROM works WHERE first_seen >= ? GROUP BY origin',
                                    (started or '9999',)).fetchall()
    spend = store.db.execute('SELECT COALESCE(SUM(charged),0) s, COUNT(*) n FROM llm_requests WHERE run=?', (run_id,)).fetchone()
    report = {
        'run': run_id, 'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'rubric': version,
        'status_counts': counts, 'new_works_by_origin': {r['origin']: r['n'] for r in new_this_run},
        'llm': {'requests': spend['n'], 'spend_upper_usd': round(spend['s'] / 1e9, 4)},
        'watermarks': {r['name']: r['value'] for r in store.db.execute('SELECT name, value FROM watermarks ORDER BY name')},
        'accepted': [{k: v for k, v in item.items() if k != 'record'} for item in (outcome or {}).get('accepted', [])],
        'review_queue': review, 'unknown_venues': unknown_rows[:60],
        'promotion': {k: len(v) for k, v in (outcome or {}).items()},
    }
    folder = OUT / run_id
    write_json(folder / 'report.json', report)
    (folder / 'report.md').write_text(render_markdown(report), encoding='utf-8')
    log(f'report: {folder / "report.md"}')
    return report


def render_markdown(r):
    lines = [f"# EcomCrypt 月度更新 {r['run']}", '', f"筛选标准 {r['rubric']}（见 SCREENING.md）。LLM 费用上界 ${r['llm']['spend_upper_usd']}，请求 {r['llm']['requests']} 次。", '']
    lines += ['## 本次新进入候选库', ''] + [f'- {k}: {v}' for k, v in sorted(r['new_works_by_origin'].items())] + ['']
    lines += ['## 状态分布（按去重后的作品计）', '', '| 状态 | 数量 |', '| --- | --- |'] + [f'| {k} | {v} |' for k, v in r['status_counts'].items()] + ['']
    if r['accepted']:
        lines += [f"## 拟收录 / 已收录（{len(r['accepted'])}）", '', '| 题名 | venue | 主题 | 理由 |', '| --- | --- | --- | --- |']
        for a in r['accepted']:
            lines.append(f"| {a['title']} | {a.get('venue') or ''} | {', '.join(a.get('topics') or [])} | {(a['screen'].get('reason') or '')[:160]} |")
        lines.append('')
    lines += [f"## 人工复核队列（{len(r['review_queue'])}）", '', '只有这里需要人看；其余决定均已留痕，可在 data/screening_ledger_v2.jsonl 追溯。', '',
              '| 状态 | 题名 | 年 | venue | 原因 |', '| --- | --- | --- | --- | --- |']
    for row in r['review_queue'][:300]:
        lines.append(f"| {row['status']} | {row['title']} | {row['year'] or ''} | {row['venue'] or ''} | {(row['reason'] or '')[:120]} |")
    lines += ['', '## 未登记 venue（只列有交叉领域题名的候选；每个 venue 决定一次）', '',
              '在 data/venue_registry_v1.json 登记即放行，在 data/venue_policy_v2.json 拒收即永久跳过；下次运行自动重新分流。', '',
              '| venue | 候选数 | 示例 |', '| --- | --- | --- |']
    for row in r['unknown_venues']:
        lines.append(f"| {row['venue']} | {row['count']} | {' / '.join(t[:70] for t in row['examples'])} |")
    return '\n'.join(lines) + '\n'


# --- editorial decisions ---------------------------------------------------

EDITORIAL = ROOT / 'data/editorial_decisions_v2.json'


def apply_editorial(store):
    """Replay git-tracked human decisions; they override model screens for the same work."""
    if not EDITORIAL.exists():
        return 0
    version = rubric.version()
    n = 0
    with store.tx():
        for row in read_json(EDITORIAL)['records']:
            keys = store.lookup([row['alias']])
            if not keys:
                continue
            key = sorted(keys)[0]
            include = row['decision'] == 'include'
            result = {'decision': row['decision'], 'code': row.get('code'), 'crossing': row.get('crossing'),
                      'topics': row.get('topics', []), 'confidence': 'high', 'reason': row.get('note', ''),
                      'evidence_T': '', 'evidence_E': '', 'editorial': True}
            current, _ = store.screen(key, 'abstract', version)
            if current != result:
                store.save_screen(key, 'abstract', version, 'editorial', 'editorial', result)
            work = store.work(key)
            if work['status'] not in TERMINAL:
                store.set_status(key, 'screen_include' if include else 'screen_exclude', 'editorial: ' + row.get('note', '')[:200])
            n += 1
    return n


def cmd_decide(args, store, config):
    """Record a human decision for one work (by DOI, arXiv ID, DBLP key, OpenAlex ID or exact title)."""
    alias = args.id
    if not alias.startswith(('doi:', 'arxiv:', 'dblp:', 'openalex:', 't:', 'iacr-eprint:')):
        from metadata import normalize_doi
        alias = ('doi:' + normalize_doi(alias)) if normalize_doi(alias) else ('t:' + normalize_title(alias))
    if not store.lookup([alias]):
        raise SystemExit(f'No work in the store matches {alias}')
    document = read_json(EDITORIAL) if EDITORIAL.exists() else {'schema_version': 1, 'records': []}
    document['records'] = [r for r in document['records'] if r['alias'] != alias]
    document['records'].append({'alias': alias, 'decision': args.decision, 'topics': args.topic or [], 'code': args.code,
                                'note': args.note or '', 'date': date.today().isoformat()})
    write_json(EDITORIAL, document)
    log(f'decide: {alias} -> {args.decision} ({apply_editorial(store)} editorial decisions applied)')


# --- durable export ---------------------------------------------------------

def cmd_export(args, store, config):
    rows = []
    for work in store.works():
        screens = store.db.execute('SELECT stage, rubric, input_hash, model, result, at FROM screens WHERE key=? ORDER BY stage, at', (work['key'],)).fetchall()
        if not screens and work['status'] not in {'promoted'}:
            continue
        aliases = [r['alias'] for r in store.db.execute('SELECT alias FROM aliases WHERE key=? ORDER BY alias', (work['key'],))]
        rows.append({'key': work['key'], 'title': work['title'], 'year': work['year'], 'venue': work['venue'],
                     'status': work['status'], 'aliases': aliases,
                     'screens': [{**{k: s[k] for k in ('stage', 'rubric', 'input_hash', 'model', 'at')}, 'result': json.loads(s['result'])} for s in screens]})
    rows.sort(key=lambda r: r['key'])
    with open(EXPORT, 'w', encoding='utf-8', newline='\n') as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
    log(f'export: {len(rows)} screened works -> {EXPORT}')


def cmd_restore(args, store, config):
    if not EXPORT.exists():
        raise SystemExit('No export file to restore from.')
    n = 0
    with open(EXPORT, encoding='utf-8') as handle:
        for line in handle:
            row = json.loads(line)
            record = {'source': 'restore', 'source_id': row['key'], 'title': row['title'], 'year': row['year'], 'venue': row['venue']}
            for alias in row['aliases']:
                kind, _, value = alias.partition(':')
                if kind == 'doi':
                    record['doi'] = value
                elif kind == 'arxiv':
                    record['arxiv'] = value
                elif kind not in {'t', 'directory'}:
                    record.setdefault('source_ids', {})[kind] = value
            key, _ = store.add(record, origin='restore')
            with store.tx():
                for s in row['screens']:
                    store.save_screen(key, s['stage'], s['rubric'], s['input_hash'], s['model'], s['result'])
            n += 1
    log(f'restore: {n} works with screening history restored')
    refresh(store)


def cmd_status(args, store, config):
    print(json.dumps({'counts': store.counts(),
                      'watermarks': {r['name']: r['value'] for r in store.db.execute('SELECT name, value FROM watermarks')}},
                     ensure_ascii=False, indent=2))


def cmd_run(args, store, config, run_id):
    started = datetime.now(timezone.utc).isoformat(timespec='seconds')
    if not store.get_mark('legacy_import'):
        cmd_init(args, store, config)
    else:
        sync_directory(store)
    apply_editorial(store)
    if not args.skip_feeds:
        cmd_feeds(argparse.Namespace(only=None), store, config)
    else:
        _KNOWN['names'] = directory_index(current_directory(), config['dblp']['known_author_min_papers'])['known_author_names']
        refresh(store)
    cmd_screen(argparse.Namespace(stage='all', budget=args.budget, limit=None, no_enrich=False, min_year=args.min_year, group=args.group), store, config, run_id)
    outcome = cmd_promote(argparse.Namespace(apply=args.apply), store, config)
    cmd_export(args, store, config)
    build_report(store, run_id, outcome, started)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--store', type=Path, default=ROOT / '.cache/pipeline/store.sqlite')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init', help='sync directory, import legacy caches, classify')
    p = sub.add_parser('dblp', help='ingest a monthly DBLP XML release')
    p.add_argument('--file'); p.add_argument('--release'); p.add_argument('--download', action='store_true'); p.add_argument('--force', action='store_true')
    p = sub.add_parser('feeds', help='incremental OpenAlex / arXiv / IACR ePrint harvest')
    p.add_argument('--only', action='append', choices=['openalex', 'arxiv', 'eprint'])
    sub.add_parser('refresh', help='re-sync directory and recompute venue/prefilter status (after editing registry/policy)')
    p = sub.add_parser('enrich', help='recover abstracts')
    p.add_argument('--status', action='append'); p.add_argument('--limit', type=int)
    p = sub.add_parser('screen', help='LLM screening')
    p.add_argument('--stage', choices=['title', 'enrich', 'abstract', 'all'], default='all')
    p.add_argument('--budget', type=float); p.add_argument('--limit', type=int); p.add_argument('--no-enrich', action='store_true')
    p.add_argument('--min-year', type=int, help='only send works from this year onward to the LLM')
    p.add_argument('--with-abstract', action='store_true', help='abstract stage: only works that already have an abstract')
    p.add_argument('--retry-invalid', action='store_true', help='re-judge abstracts downgraded because an excerpt failed validation')
    p.add_argument('--group', action='append', help='only send works in this venue group to the LLM (repeatable)')
    p = sub.add_parser('promote', help='verify includes and (with --apply) append them to the ledger')
    p.add_argument('--apply', action='store_true')
    p.add_argument('--confidence', choices=['high', 'medium'], help='with --apply: write only this screening confidence')
    p.add_argument('--kind', choices=['formal', 'preprint'], help='with --apply: write only formal publications or only preprints')
    p.add_argument('--group', action='append', help='with --apply: write only this venue group (repeatable)')
    p = sub.add_parser('topics', help='assign directory papers to the display taxonomy (data/topic_taxonomy_v2.json); then run build.py build')
    p.add_argument('--budget', type=float)
    sub.add_parser('report', help='write .out/monthly/<run>/report.md')
    sub.add_parser('export', help='write data/screening_ledger_v2.jsonl')
    sub.add_parser('restore', help='rebuild screening memory from data/screening_ledger_v2.jsonl')
    sub.add_parser('status', help='print status counts and watermarks')
    p = sub.add_parser('decide', help='record a human include/exclude decision (data/editorial_decisions_v2.json)')
    p.add_argument('id', help='DOI, arxiv:ID, dblp:KEY, openalex:W.., or exact title')
    p.add_argument('decision', choices=['include', 'exclude'])
    p.add_argument('--topic', action='append'); p.add_argument('--code'); p.add_argument('--note')
    p = sub.add_parser('run', help='feeds + screen + promote + export + report')
    p.add_argument('--apply', action='store_true'); p.add_argument('--budget', type=float); p.add_argument('--skip-feeds', action='store_true')
    p.add_argument('--min-year', type=int, help='only send works from this year onward to the LLM')
    p.add_argument('--group', action='append', help='only send works in this venue group to the LLM (repeatable)')
    args = parser.parse_args(argv)
    config = load_config()
    store = Store(args.store)
    run_id = date.today().isoformat()
    from screen import LLMError
    try:
        if args.command == 'refresh':
            directory = sync_directory(store)
            _KNOWN['names'] = directory_index(directory, config['dblp']['known_author_min_papers'])['known_author_names']
            refresh(store)
        elif args.command == 'screen':
            cmd_screen(args, store, config, run_id)
        elif args.command == 'run':
            cmd_run(args, store, config, run_id)
        elif args.command == 'topics':
            cmd_topics(args, store, config, run_id)
        elif args.command == 'report':
            build_report(store, run_id)
        else:
            globals()['cmd_' + args.command](args, store, config)
    except LLMError as error:
        raise SystemExit(f'monthly: {error}') from None
    finally:
        store.close()


if __name__ == '__main__':
    main()
