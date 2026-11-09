"""Batch abstract recovery for candidates that survived the prefilter.

Order (cheapest / most complete first): records already carrying an abstract ->
OpenAlex DOI batch (50/request) -> Semantic Scholar batch (500/request; key
optional but strongly recommended) -> arXiv id_list (100/request) -> Crossref per
DOI (only what is still missing). Recovered venue names also feed the venue gate.
Missing abstracts are not evidence of irrelevance; such works still get a
title-level decision and, if plausible, land in the needs_fulltext queue.
"""
import json
import os
import re
from urllib.parse import quote, urlencode

from metadata import normalize_doi
from source_feeds import FeedError, _fetch_public, arxiv_by_ids
from store import arxiv_id


def _inverted(index):
    words = sorted((p, w) for w, ps in (index or {}).items() for p in ps)
    return ' '.join(w for _, w in words)


def _strip_jats(text):
    return ' '.join(re.sub(r'<[^>]+>', ' ', text or '').split())


def _ids(store, key):
    out = {'doi': None, 'arxiv': None, 'openalex': None}
    for row in store.db.execute('SELECT alias FROM aliases WHERE key=?', (key,)):
        kind, _, value = row['alias'].partition(':')
        if kind in out and not out[kind]:
            out[kind] = value
    return out


def enrich(store, http, keys, *, s2_key=None, use_crossref=True, log=print):
    """Fill abstracts (and venue hints) for the given work keys. Returns counters."""
    stats = {'requested': len(keys), 'openalex': 0, 's2': 0, 'arxiv': 0, 'crossref': 0, 'errors': []}
    def missing():
        return [k for k in keys if len((store.work(k) or {}).get('abstract') or '') < 200]
    # 1. editions that already carry abstracts (arXiv / ePrint / OpenAlex harvests)
    for key in keys:
        for edition in store.editions(key):
            if edition.get('abstract'):
                store.set_abstract(key, edition['abstract'], edition.get('source', 'edition'))
    # 2. OpenAlex by DOI
    todo = [(k, i['doi']) for k in missing() if (i := _ids(store, k))['doi'] and not set(i['doi']) & {',', '|'}]
    for start in range(0, len(todo), 50):
        chunk = todo[start:start + 50]
        public = 'https://api.openalex.org/works?' + urlencode({
            'filter': 'doi:' + '|'.join(d for _, d in chunk), 'per_page': 50,
            'select': 'id,doi,abstract_inverted_index,primary_location'})
        url = public + (('&' + urlencode({'api_key': os.environ['OPENALEX_API_KEY']})) if os.environ.get('OPENALEX_API_KEY') else '')
        try:
            payload = json.loads(_fetch_public(http, url, public))
        except (FeedError, ValueError) as error:
            stats['errors'].append(f'openalex:{error}')
            break
        by_doi = {normalize_doi(r.get('doi')): r for r in payload.get('results') or []}
        for key, doi in chunk:
            raw = by_doi.get(doi)
            if not raw:
                continue
            text = _inverted(raw.get('abstract_inverted_index'))
            if text:
                store.set_abstract(key, text, 'openalex')
                stats['openalex'] += 1
            venue = ((raw.get('primary_location') or {}).get('source') or {}).get('display_name')
            if venue:
                store.db.execute("UPDATE works SET venue=COALESCE(NULLIF(venue,''), ?) WHERE key=?", (venue, key))
                store.db.execute('INSERT OR IGNORE INTO aliases VALUES (?, ?)', ('openalex:' + raw['id'].rsplit('/', 1)[-1], key))
    # 3. Semantic Scholar batch
    todo = []
    for key in missing():
        i = _ids(store, key)
        if i['doi']:
            todo.append((key, 'DOI:' + i['doi']))
        elif i['arxiv']:
            todo.append((key, 'ARXIV:' + i['arxiv']))
    headers = {'Content-Type': 'application/json', **({'x-api-key': s2_key} if s2_key else {})}
    for start in range(0, len(todo), 500):
        chunk = todo[start:start + 500]
        url = 'https://api.semanticscholar.org/graph/v1/paper/batch?fields=abstract,tldr,venue,year,externalIds'
        try:
            rows = json.loads(http.fetch(url, headers=headers, body=json.dumps({'ids': [i for _, i in chunk]})))
        except (FeedError, ValueError) as error:
            stats['errors'].append(f's2:{error}')
            break
        for (key, _), row in zip(chunk, rows if isinstance(rows, list) else []):
            if not row:
                continue
            tldr = ((row.get('tldr') or {}).get('text')) or None
            if row.get('abstract') or tldr:
                store.set_abstract(key, row.get('abstract') or '', 's2', tldr=tldr)
                stats['s2'] += bool(row.get('abstract'))
    # 4. arXiv by ID
    todo = {i['arxiv']: k for k in missing() if (i := _ids(store, k))['arxiv']}
    if todo:
        try:
            for record in arxiv_by_ids(http, sorted(todo)):
                key = todo.get(arxiv_id(record['source_id']))
                if key and record.get('abstract'):
                    store.set_abstract(key, record['abstract'], 'arxiv')
                    stats['arxiv'] += 1
        except FeedError as error:
            stats['errors'].append(f'arxiv:{error}')
    # 5. Crossref, one DOI at a time, only for what is still missing
    if use_crossref:
        mail = os.environ.get('CROSSREF_MAILTO') or os.environ.get('METADATA_CONTACT')
        for key in missing():
            doi = _ids(store, key)['doi']
            if not doi:
                continue
            public = f'https://api.crossref.org/works/{quote(doi, safe="/")}'
            url = public + (('?' + urlencode({'mailto': mail})) if mail else '')
            try:
                message = json.loads(_fetch_public(http, url, public)).get('message') or {}
            except (FeedError, ValueError):
                continue
            if message.get('abstract'):
                store.set_abstract(key, _strip_jats(message['abstract']), 'crossref')
                stats['crossref'] += 1
    # 6. Resolve book-series / missing venues to the actual event via Crossref (cached).
    unresolved = [k for k in keys if (store.work(k) or {}).get('venue_decision') == 'unresolved' and _ids(store, k)['doi']]
    if use_crossref and unresolved:
        from metadata import _crossref_record
        mail = os.environ.get('CROSSREF_MAILTO') or os.environ.get('METADATA_CONTACT')
        stats['venue_resolved'] = 0
        for key in unresolved:
            doi = _ids(store, key)['doi']
            public = f'https://api.crossref.org/works/{quote(doi, safe="/")}'
            url = public + (('?' + urlencode({'mailto': mail})) if mail else '')
            try:
                message = json.loads(_fetch_public(http, url, public)).get('message') or {}
            except (FeedError, ValueError):
                continue
            record = _crossref_record(message)
            if record.get('venue') and record.get('source_id'):
                store.add(record, origin='crossref')
                stats['venue_resolved'] += 1
    stats['still_missing'] = len(missing())
    log(f"enrich: {stats['requested']} works; openalex={stats['openalex']} s2={stats['s2']} arxiv={stats['arxiv']} "
        f"crossref={stats['crossref']} still_missing={stats['still_missing']}" + (f" errors={stats['errors']}" if stats['errors'] else ''))
    return stats
