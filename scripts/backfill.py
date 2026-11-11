"""Backfill registered journals that DBLP does not cover (economics, finance, OR/MS, information systems).

The monthly OpenAlex keyword lanes only reach back to feeds.initial_since. Searching all of OpenAlex
from 2008 would mostly return unrelated work, so this harvest restricts the same keyword queries to
the journals in the registry. Journal names are first resolved to OpenAlex source IDs, which are
written back into data/venue_registry_v1.json (source_ids, selector_status).
"""
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

import source_feeds as feeds

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / 'data/venue_registry_v1.json'
GROUPS = {'Econ', 'Finance', 'OR/MS', 'Interdisciplinary'}


def _norm(text):
    text = ''.join(ch for ch in unicodedata.normalize('NFKD', text or '') if not unicodedata.category(ch).startswith('M'))
    text = re.sub(r'&', ' and ', text.lower())
    return ' '.join(word for word in re.sub(r'[^a-z0-9]+', ' ', text).split() if word != 'the')


def targets(registry):
    """Journals to backfill, micro theory / game theory / mechanism design first, then other top journals."""
    from venue_policy import queue_rank
    rows = [row for row in registry['venues'] if row['kind'] == 'journal' and (row['group'] in GROUPS or not row.get('dblp'))]
    return sorted(rows, key=lambda row: queue_rank(row['name']))


class QuotaExhausted(RuntimeError):
    pass


def _quota(error):
    text = str(error)
    return '429' in text or 'Insufficient budget' in text or 'Rate limit' in text


def resolve(http, rows, log=print):
    """Find each journal's OpenAlex source ID by exact (normalized) name. Returns how many were newly resolved."""
    import os
    key = os.environ.get('OPENALEX_API_KEY')
    resolved = 0
    for row in rows:
        if row.get('source_ids'):
            continue
        public = 'https://api.openalex.org/sources?' + urlencode({'search': row['name'], 'per_page': 10, 'select': 'id,display_name,alternate_titles,type,works_count'})
        url = public + ('&' + urlencode({'api_key': key}) if key else '')
        try:
            payload = json.loads(feeds._fetch_public(http, url, public))
        except (feeds.FeedError, ValueError) as error:
            if _quota(error):
                raise QuotaExhausted(f'OpenAlex quota exhausted at {row["label"]}; rerun after it resets (midnight UTC)') from error
            log(f'backfill: {row["label"]}: lookup failed ({error})')
            continue
        wanted = _norm(row['name'])
        hits = [s for s in payload.get('results') or [] if s.get('type') == 'journal'
                and wanted in {_norm(s.get('display_name')), *(_norm(t) for t in s.get('alternate_titles') or [])}]
        if hits:
            best = max(hits, key=lambda s: s.get('works_count') or 0)
            row['source_ids'] = [best['id'].rsplit('/', 1)[-1]]
            row['selector_status'] = 'resolved'
            resolved += 1
        else:
            row['selector_status'] = 'no_exact_openalex_source'
    return resolved


def harvest(http, store, config, rows, *, since, until, log=print):
    """Keyword lanes restricted to the resolved journals; returns the keys of new works."""
    ids = [source for row in rows for source in row.get('source_ids') or []]
    touched, total = [], 0
    for start in range(0, len(ids), 40):
        chunk = ids[start:start + 40]
        for i, query in enumerate(config['openalex']['keyword_queries']):
            expr = (f'from_publication_date:{since},to_publication_date:{until},'
                    f'primary_location.source.id:{"|".join(chunk)},title_and_abstract.search:{query}')
            try:
                for record in feeds.openalex_pages(http, expr, max_pages=config['openalex']['max_pages_per_lane']):
                    key, is_new = store.add(record, origin=f'openalex:backfill{i}', abstract=record.get('abstract'))
                    total += 1
                    if is_new:
                        touched.append(key)
            except feeds.FeedError as error:
                if _quota(error):
                    log(f'backfill: OpenAlex quota exhausted at sources {start}-{start + len(chunk)}; stopping, {len(touched)} new works kept')
                    return touched
                log(f'backfill: sources {start}-{start + len(chunk)} query {i} stopped ({error})')
    log(f'backfill: {len(ids)} journals, {total} records, {len(touched)} new works ({since} to {until})')
    return touched


def run(store, config, *, since, until, log=print):
    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
    rows = targets(registry)
    http = feeds.Http()
    try:
        newly = resolve(http, rows, log=log)
    finally:                                    # keep whatever was resolved before a quota stop
        REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    missing = [row['label'] for row in rows if not row.get('source_ids')]
    log(f'backfill: {len(rows)} journals, {newly} newly resolved, {len(missing)} without an exact OpenAlex source: {", ".join(missing[:40])}')
    touched = harvest(http, store, config, rows, since=since, until=until, log=log)
    store.set_mark('backfill:journals', date.today().isoformat())
    return touched


# --- Semantic Scholar bulk search (no daily quota; used when OpenAlex is exhausted) -------------------------

S2_BULK = 'https://api.semanticscholar.org/graph/v1/paper/search/bulk'
S2_FIELDS = "title,abstract,authors,year,venue,publicationVenue,externalIds,publicationDate,url"


def s2_query(openalex_query):
    """OpenAlex boolean text -> Semantic Scholar bulk syntax (| for OR, quoted phrases kept)."""
    return re.sub(r'\s+OR\s+', ' | ', openalex_query)


def _s2_record(raw):
    ids = raw.get('externalIds') or {}
    doi = (ids.get('DOI') or '').lower() or None
    venue = (raw.get('publicationVenue') or {}).get('name') or raw.get('venue') or None
    return {'source': 's2', 'source_id': raw['paperId'], 'source_url': f"https://www.semanticscholar.org/paper/{raw['paperId']}",
            'title': raw.get('title'), 'year': raw.get('year'), 'doi': doi, 'venue': venue,
            'authors': [{'name': a.get('name')} for a in raw.get('authors') or [] if a.get('name')],
            'url': f'https://doi.org/{doi}' if doi else raw.get('url'), 'kind': 'journal-article',
            'arxiv': ids.get('ArXiv'), 'abstract': raw.get('abstract')}


def s2_pages(http, *, query, venues, since, until, key=None, max_pages=50):
    token = None
    headers = {'x-api-key': key} if key else {}
    for _ in range(max_pages):
        params = {'query': query, 'venue': ','.join(venues), 'publicationDateOrYear': f'{since}:{until}', 'fields': S2_FIELDS}
        if token:
            params['token'] = token
        payload = json.loads(http.fetch(S2_BULK + '?' + urlencode(params), headers=headers))
        for raw in payload.get('data') or []:
            if raw.get('title') and raw.get('paperId'):
                yield _s2_record(raw)
        token = payload.get('token')
        if not token:
            return


def run_s2(store, config, *, since, until, log=print):
    """Same keyword lanes, restricted by venue name, through Semantic Scholar. Returns the keys of new works."""
    import os
    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
    rows = targets(registry)
    http = feeds.Http()
    key = os.environ.get('S2_API_KEY')
    queries = [s2_query(q) for q in config['openalex']['keyword_queries']]
    from urllib.parse import quote
    mail = os.environ.get('CROSSREF_MAILTO')
    rows = [row for row in rows if row.get('issn')]          # only journals whose ISSNs are pinned in the registry
    touched, total, dropped = [], 0, 0
    for start in range(0, len(rows), 10):                 # targets() is already in queue order: micro theory first
        chunk = rows[start:start + 10]
        names = [name for row in chunk for name in [row['name'], *row.get('aliases', [])] if ',' not in name]
        issns = {issn: row for row in chunk for issn in row['issn']}
        for i, query in enumerate(queries):
            try:
                for record in s2_pages(http, query=query, venues=names, since=since, until=until, key=key):
                    # S2 conflates journals of similar names, ISSNs included; the DOI's Crossref ISSNs decide.
                    if not record.get('doi') or record['doi'].startswith(('10.48550/', '10.2139/')):
                        dropped += 1
                        continue
                    try:
                        url = 'https://api.crossref.org/works/' + quote(record['doi'], safe='/') + (f'?mailto={quote(mail)}' if mail else '')
                        message = json.loads(http.fetch(url)).get('message') or {}
                    except (feeds.FeedError, ValueError):
                        message = {}
                    row = next((issns[x] for x in message.get('ISSN') or [] if x in issns), None)
                    if row is None:
                        dropped += 1
                        continue
                    record['venue'] = row['name']
                    record['kind'] = 'journal-article'
                    k, is_new = store.add(record, origin=f's2:backfill{i}', abstract=record.get('abstract'))
                    total += 1
                    if is_new:
                        touched.append(k)
            except (feeds.FeedError, ValueError) as error:
                log(f'backfill-s2: {chunk[0]["label"]}.. query {i} stopped ({error})')
        log(f'backfill-s2: journals {start + 1}-{start + len(chunk)} ({", ".join(r["label"] for r in chunk)}): {total} records kept, {dropped} dropped, {len(touched)} new so far')
    store.set_mark('backfill:s2', date.today().isoformat())
    return touched


def venue_matches(venue, rows):
    """S2's venue filter is loose; keep only records whose venue is one of the requested journals."""
    wanted = {_norm(name) for row in rows for name in [row['name'], *row.get('aliases', [])]}
    return _norm(venue) in wanted


# --- Scopus search (Elsevier API key; covers every major publisher; ISSN-exact) ------------------------------

SCOPUS = 'https://api.elsevier.com/content/search/scopus'


def scopus_query(openalex_query):
    """OpenAlex boolean text -> a Scopus TITLE-ABS-KEY clause (same OR syntax, quoted phrases kept)."""
    return f'TITLE-ABS-KEY({openalex_query})'


def _scopus_record(entry, venue):
    doi = (entry.get('prism:doi') or '').lower() or None
    year = (entry.get('prism:coverDate') or '')[:4]
    return {'source': 'scopus', 'source_id': entry.get('eid'), 'source_url': next((l['@href'] for l in entry.get('link') or [] if l.get('@ref') == 'scopus'), None),
            'title': entry.get('dc:title'), 'year': int(year) if year.isdigit() else None, 'doi': doi, 'venue': venue,
            # STANDARD view lists only the first author; an incomplete byline would read as a mismatch, so authors come
            # from the Crossref edition and Scopus corroborates title, year and journal.
            'authors': [], 'first_author': entry.get('dc:creator'),
            'url': f'https://doi.org/{doi}' if doi else None, 'kind': 'journal-article'}


def scopus_pages(http, query, key, max_results=2000):
    for start in range(0, max_results, 25):
        url = SCOPUS + '?' + urlencode({'query': query, 'count': 25, 'start': start, 'field': 'dc:title,dc:creator,prism:publicationName,prism:coverDate,prism:doi,eid,prism:issn,prism:eIssn,link'})
        payload = json.loads(http.fetch(url, headers={'X-ELS-APIKey': key, 'Accept': 'application/json'}))
        result = payload.get('search-results') or {}
        entries = [e for e in result.get('entry') or [] if not e.get('error')]
        yield from entries
        if start + 25 >= int(result.get('opensearch:totalResults') or 0) or not entries:
            return


def run_scopus(store, config, *, since, until, log=print):
    """Keyword lanes per journal through Scopus, by ISSN. Each hit with a DOI also gets its Crossref record as a second edition."""
    import os
    from metadata import MetadataClient, MetadataError
    key = os.environ.get('ELSEVIER_API_KEY')
    if not key:
        raise SystemExit('ELSEVIER_API_KEY is not set (run through monthly.ps1)')
    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
    rows = [row for row in targets(registry) if row.get('issn')]
    http = feeds.Http()
    http.spacing['api.elsevier.com'] = 0.2
    crossref = MetadataClient(ROOT / '.cache/metadata')
    years = f'PUBYEAR > {int(since[:4]) - 1} AND PUBYEAR < {int(until[:4]) + 1}'
    touched, total, no_doi = [], 0, 0
    for n, row in enumerate(rows, 1):
        issns = ' OR '.join(f'ISSN({issn})' for issn in row['issn'])
        found = 0
        for i, lane in enumerate(config['openalex']['keyword_queries']):
            query = f'({issns}) AND {scopus_query(lane)} AND {years}'
            try:
                for entry in scopus_pages(http, query, key):
                    record = _scopus_record(entry, row['name'])
                    if not record['doi'] or not record['title']:
                        no_doi += 1
                        continue
                    k, is_new = store.add(record, origin=f'scopus:backfill{i}')
                    try:
                        for extra in crossref.lookup_crossref(record['doi'])[:1]:
                            store.add({**extra, 'venue': extra.get('venue') or row['name']}, origin='crossref')
                    except (MetadataError, ValueError):
                        pass
                    total += 1
                    found += 1
                    if is_new:
                        touched.append(k)
            except (feeds.FeedError, ValueError) as error:
                log(f'backfill-scopus: {row["label"]} query {i} stopped ({error})')
                if '429' in str(error):
                    log('backfill-scopus: quota exhausted; stopping')
                    store.set_mark('backfill:scopus', date.today().isoformat())
                    return touched
        if found or n % 20 == 0:
            log(f'backfill-scopus: {n}/{len(rows)} {row["label"]}: {found} hits; {total} records, {len(touched)} new so far')
    log(f'backfill-scopus: done; {total} records, {len(touched)} new works, {no_doi} hits without DOI skipped')
    store.set_mark('backfill:scopus', date.today().isoformat())
    return touched
