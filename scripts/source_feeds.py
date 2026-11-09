"""Incremental machine-readable feeds: OpenAlex, arXiv API, IACR ePrint OAI-PMH.

Every lane keeps a date watermark in the store; a lane's watermark only advances
after the lane finishes, so an interrupted month resumes instead of skipping.
Raw pages are cached under .cache/pipeline/raw/ for audit and crash recovery.
"""
import hashlib
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from metadata import _openalex_record, normalize_doi

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / '.cache/pipeline/raw'
AGENT = 'EconCS-Directory/2.0 (research directory; monthly incremental harvest)'
OPENALEX_SELECT = ('id,doi,title,publication_year,primary_location,locations,type,authorships,'
                   'is_retracted,abstract_inverted_index,ids,created_date')


class FeedError(RuntimeError):
    pass


class Http:
    """Polite GET/POST with per-host spacing, retry on 429/5xx, and raw caching."""

    def __init__(self, spacing=None, cache=RAW, offline=False):
        self.spacing = {'api.openalex.org': 0.15, 'export.arxiv.org': 3.1, 'eprint.iacr.org': 1.0,
                        'api.semanticscholar.org': 1.1, 'api.crossref.org': 0.25, **(spacing or {})}
        self.last = {}
        self.cache = Path(cache)
        self.offline = offline

    def _cache_path(self, url, body):
        digest = hashlib.sha256((url + '\n' + (body or '')).encode()).hexdigest()
        return self.cache / url.split('/')[2] / f'{digest}.raw'

    def fetch(self, url, *, headers=None, body=None, cache=True, attempts=4):
        path = self._cache_path(url, body)
        if cache and path.exists():
            return path.read_bytes()
        if self.offline:
            raise FeedError('offline_cache_miss')
        host = url.split('/')[2]
        for attempt in range(attempts):
            wait = self.last.get(host, 0) + self.spacing.get(host, 0.5) - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self.last[host] = time.monotonic()
            request = Request(url, data=body.encode() if body else None,
                              headers={'User-Agent': AGENT, 'Accept': '*/*', **(headers or {})})
            try:
                with urlopen(request, timeout=90) as response:
                    data = response.read(64 * 1024 * 1024)
                break
            except HTTPError as error:
                code = error.code
                retry = error.headers.get('Retry-After') if error.headers else None
                error.close()
                if code in {429, 500, 502, 503, 504} and attempt + 1 < attempts:
                    time.sleep(min(120, float(retry) if (retry or '').isdigit() else 5 * 2 ** attempt))
                    continue
                raise FeedError(f'http_{code}') from None
            except (URLError, OSError):
                if attempt + 1 < attempts:
                    time.sleep(5 * 2 ** attempt)
                    continue
                raise FeedError('network_error') from None
        if cache:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return data


# --- OpenAlex ---------------------------------------------------------------

def openalex_pages(http, filter_expr, *, max_pages=200, per_page=200, search=None):
    """Yield (record, raw) for every work matching filter_expr (cursor pagination)."""
    cursor = '*'
    key = os.environ.get('OPENALEX_API_KEY')
    mail = os.environ.get('CROSSREF_MAILTO') or os.environ.get('METADATA_CONTACT')
    for _ in range(max_pages):
        params = {'filter': filter_expr, 'select': OPENALEX_SELECT, 'per_page': per_page, 'cursor': cursor}
        if search:
            params['search'] = search
        url = 'https://api.openalex.org/works?' + urlencode(params)
        public = url
        if key:
            url += '&' + urlencode({'api_key': key})
        elif mail:
            url += '&' + urlencode({'mailto': mail})
        payload = json.loads(_fetch_public(http, url, public))
        for raw in payload.get('results') or []:
            record = _openalex_record(raw)
            ids = raw.get('ids') or {}
            if not record.get('doi') and ids.get('doi'):
                record['doi'] = normalize_doi(ids['doi'])
            record['created_date'] = raw.get('created_date')
            if record.get('title') and record.get('source_id'):
                yield record
        cursor = (payload.get('meta') or {}).get('next_cursor')
        if not cursor or not payload.get('results'):
            return
    raise FeedError('openalex_page_limit')


def _fetch_public(http, url, public):
    """Cache under the key-free URL so API keys never land on disk."""
    path = http._cache_path(public, None)
    if path.exists():
        return path.read_bytes()
    data = http.fetch(url, cache=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def openalex_keyword_lanes(config, since):
    """(lane, filter_expr) keyword lanes for one window."""
    window = f"{config['openalex'].get('date_filter', 'from_publication_date')}:{since}"
    return [(f'openalex:kw{i}', f'{window},title_and_abstract.search:{q}') for i, q in enumerate(config['openalex']['keyword_queries'])]


def openalex_id_filter(config, kind, ids, since):
    """Filter for works citing (kind='cites') or authored by (kind='authorships.author.id') up to 80 IDs."""
    window = f"{config['openalex'].get('date_filter', 'from_publication_date')}:{since}"
    return f"{window},{kind}:" + '|'.join(ids)


# --- arXiv -----------------------------------------------------------------

ATOM = {'a': 'http://www.w3.org/2005/Atom', 'x': 'http://arxiv.org/schemas/atom'}


def parse_arxiv(raw):
    root = ET.fromstring(raw)
    for entry in root.findall('a:entry', ATOM):
        text = lambda tag: ' '.join((entry.findtext(tag, default='', namespaces=ATOM)).split())
        identifier = re.sub(r'v\d+$', '', text('a:id').rsplit('/abs/', 1)[-1])
        if not identifier:
            continue
        doi = normalize_doi(text('x:doi'))
        yield {'source': 'arxiv', 'source_id': identifier, 'title': text('a:title'),
               'year': int(text('a:published')[:4]) if text('a:published')[:4].isdigit() else None,
               'venue': 'arXiv', 'kind': 'preprint', 'doi': None, 'published_doi': doi,
               'related_dois': [doi] if doi else [], 'url': f'https://arxiv.org/abs/{identifier}',
               'source_url': f'https://arxiv.org/abs/{identifier}', 'abstract': text('a:summary')[:6000],
               'authors': [{'name': ' '.join(a.findtext('a:name', default='', namespaces=ATOM).split()), 'ids': {},
                            'institutions': []} for a in entry.findall('a:author', ATOM)],
               'categories': [c.get('term') for c in entry.findall('a:category', ATOM)],
               'journal_ref': text('x:journal_ref'),
               'is_retracted': bool(re.search(r'\bwithdrawn\b', text('x:comment'), re.I))}


def arxiv_window(http, categories, since, until, *, page=200, max_pages=100):
    cats = ' OR '.join(f'cat:{c}' for c in categories)
    span = f"submittedDate:[{since.replace('-', '')}0000 TO {until.replace('-', '')}2359]"
    for n in range(max_pages):
        params = {'search_query': f'({cats}) AND {span}', 'start': n * page, 'max_results': page,
                  'sortBy': 'submittedDate', 'sortOrder': 'ascending'}
        raw = http.fetch('https://export.arxiv.org/api/query?' + urlencode(params))
        rows = list(parse_arxiv(raw))
        yield from rows
        if len(rows) < page:
            return
    raise FeedError('arxiv_page_limit')


def arxiv_by_ids(http, ids):
    for i in range(0, len(ids), 100):
        params = {'id_list': ','.join(ids[i:i + 100]), 'max_results': 100}
        yield from parse_arxiv(http.fetch('https://export.arxiv.org/api/query?' + urlencode(params)))


# --- IACR ePrint (OAI-PMH) -------------------------------------------------

OAI = {'o': 'http://www.openarchives.org/OAI/2.0/', 'dc': 'http://purl.org/dc/elements/1.1/',
       'od': 'http://www.openarchives.org/OAI/2.0/oai_dc/'}


def parse_eprint(raw):
    root = ET.fromstring(raw)
    records = []
    for rec in root.iterfind('.//o:record', OAI):
        if (rec.find('o:header', OAI).get('status') or '') == 'deleted':
            continue
        meta = rec.find('.//od:dc', OAI)
        if meta is None:
            continue
        get = lambda tag: [' '.join((e.text or '').split()) for e in meta.findall(f'dc:{tag}', OAI)]
        url = next((v for v in get('identifier') if 'eprint.iacr.org/' in v), '')
        match = re.search(r'eprint\.iacr\.org/(\d{4}/\d+)', url)
        if not match:
            continue
        dates = get('date')
        year = int(dates[0][:4]) if dates and dates[0][:4].isdigit() else int(match[1][:4])
        dois = [d for v in get('identifier') + get('relation') if (d := normalize_doi(v))]
        records.append({'source': 'iacr-eprint', 'source_id': match[1], 'title': (get('title') or [''])[0],
                        'year': year, 'venue': 'IACR Cryptology ePrint Archive', 'kind': 'preprint', 'doi': None,
                        'published_doi': dois[0] if dois else None, 'url': f'https://eprint.iacr.org/{match[1]}',
                        'source_url': f'https://eprint.iacr.org/{match[1]}', 'abstract': ' '.join(get('description'))[:6000],
                        'authors': [{'name': n, 'ids': {}, 'institutions': []} for n in get('creator')]})
    token = root.find('.//o:resumptionToken', OAI)
    return records, (token.text.strip() if token is not None and token.text else None)


def eprint_since(http, since, *, base='https://eprint.iacr.org/oai', max_pages=500):
    params = {'verb': 'ListRecords', 'metadataPrefix': 'oai_dc', 'from': since}
    for _ in range(max_pages):
        # Resumption tokens are session-bound, so OAI pages are never replayed from cache.
        raw = http.fetch(base + '?' + urlencode(params), cache=False)
        if b'noRecordsMatch' in raw[:4000]:
            return
        records, token = parse_eprint(raw)
        yield from records
        if not token:
            return
        params = {'verb': 'ListRecords', 'resumptionToken': token}
    raise FeedError('eprint_page_limit')


def month_start(today=None, months_back=1):
    today = today or date.today()
    first = today.replace(day=1)
    for _ in range(months_back):
        first = (first - timedelta(days=1)).replace(day=1)
    return first.isoformat()
