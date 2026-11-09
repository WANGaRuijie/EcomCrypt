"""Local DBLP: stream the official monthly XML dump instead of querying dblp.org.

dblp.org blocks bulk/automated queries, but publishes the whole database as a
monthly CC0 release (dblp-YYYY-MM-01.xml.gz, ~1 GB compressed). We stream-parse
it once per release without decompressing to disk and keep only records that pass
the screening prefilter (or are by known directory authors). Nothing else is stored.
"""
import gzip
import html.entities
import re
import shutil
import time
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

from metadata import normalize_doi

RECORD_TAGS = {'article', 'inproceedings', 'incollection'}
TOP_LEVEL = RECORD_TAGS | {'proceedings', 'book', 'phdthesis', 'mastersthesis', 'www', 'data'}
DAGSTUHL = 'https://drops.dagstuhl.de/storage/artifacts/dblp/xml/{y}/dblp-{y}-{m:02d}-01.xml.gz'
DBLP_LATEST = 'https://dblp.org/xml/dblp.xml.gz'


def release_candidates(today=None, back=3):
    today = today or date.today()
    y, m = today.year, today.month
    out = []
    for _ in range(back + 1):
        out.append((f'{y}-{m:02d}-01', DAGSTUHL.format(y=y, m=m)))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return out


def download(target_dir, *, today=None, agent='EconCS-Directory/2.0 (monthly dump download)'):
    """Fetch the newest available monthly release; returns (release, path). Skips if already present."""
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    errors = []
    for release, url in release_candidates(today):
        path = target_dir / f'dblp-{release}.xml.gz'
        if path.exists() and path.stat().st_size > 100_000_000:
            return release, path
        try:
            request = Request(url, headers={'User-Agent': agent})
            with urlopen(request, timeout=60) as response, open(path.with_suffix('.part'), 'wb') as out:
                shutil.copyfileobj(response, out, length=1 << 20)
            path.with_suffix('.part').replace(path)
            return release, path
        except OSError as error:  # includes HTTPError/URLError
            path.with_suffix('.part').unlink(missing_ok=True)
            errors.append(f'{url}: {type(error).__name__} {getattr(error, "code", "")}'.strip())
    raise RuntimeError('No DBLP release could be downloaded. Download it manually from '
                       'https://drops.dagstuhl.de/entities/collection/10.4230/dblp.xml and pass --file. ' + '; '.join(errors))


_XML_ENTITIES = {'amp', 'lt', 'gt', 'quot', 'apos'}
_ENTITY = re.compile(rb'&([A-Za-z][A-Za-z0-9]*);')
_NAMED = {name: ('&#%d;' % code).encode() for name, code in html.entities.name2codepoint.items() if name not in _XML_ENTITIES}


class _EntityStream:
    """File-like filter: dblp.xml uses ISO-8859 entities defined only in dblp.dtd, which
    expat does not load. Rewrite them to numeric character references on the fly so the
    standard parser works on every Python version, with constant memory."""

    def __init__(self, raw):
        self.raw, self.tail, self.done = raw, b'', False

    def read(self, size=1 << 20):
        while True:
            data = self._read(size)
            if data or self.done:
                return data

    def _read(self, size):
        if self.done:
            return b''
        chunk = self.raw.read(size)
        if not chunk:
            self.done = True
            data, self.tail = self.tail, b''
        else:
            data = self.tail + chunk
            cut = data.rfind(b'&')
            if cut != -1 and b';' not in data[cut:] and len(data) - cut < 16:
                data, self.tail = data[:cut], data[cut:]
            else:
                self.tail = b''
        return _ENTITY.sub(lambda m: _NAMED.get(m[1].decode('ascii'), m[0]), data)


def _text(elem):
    return ' '.join(''.join(elem.itertext()).split()) if elem is not None else ''


def to_record(elem):
    key = elem.get('key') or ''
    title = _text(elem.find('title')).rstrip('.')
    ees = [_text(e) for e in elem.findall('ee')]
    doi = next((d for e in ees if (d := normalize_doi(e))), None)
    venue = _text(elem.find('journal')) or _text(elem.find('booktitle'))
    year = _text(elem.find('year'))
    authors = []
    for a in elem.findall('author'):
        name = re.sub(r' \d{4}$', '', _text(a))
        ids = {'orcid': a.get('orcid')} if a.get('orcid') else {}
        authors.append({'name': name, 'dblp_name': _text(a), 'ids': ids, 'institutions': []})
    publtype = elem.get('publtype') or ''
    kind = {'article': 'journal-article', 'inproceedings': 'proceedings-article', 'incollection': 'book-chapter'}[elem.tag]
    if key.startswith('journals/corr/') or key.startswith('journals/iacr/') or publtype == 'informal':
        kind = 'preprint'
    return {
        'source': 'dblp', 'source_id': key, 'source_url': f'https://dblp.org/rec/{key}.html',
        'title': title, 'year': int(year) if year.isdigit() else None, 'doi': doi, 'venue': venue, 'dblp_venue': venue,
        'dblp_stream': '/'.join(key.split('/')[:2]), 'kind': kind, 'authors': authors, 'ee': ees,
        'url': f'https://doi.org/{doi}' if doi else (ees[0] if ees else f'https://dblp.org/rec/{key}.html'),
        'pages': _text(elem.find('pages')) or None, 'volume': _text(elem.find('volume')) or None,
        'mdate': elem.get('mdate'), 'publtype': publtype or None, 'is_retracted': publtype == 'withdrawn' or None,
    }


def iter_records(path, *, min_year=None):
    """Yield normalized records from dblp.xml(.gz) using constant memory."""
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rb') as handle:
        context = ET.iterparse(_EntityStream(handle), events=('start', 'end'))
        _, root = next(context)
        for event, elem in context:
            if event != 'end' or elem.tag not in TOP_LEVEL:
                continue
            if elem.tag in RECORD_TAGS:
                record = to_record(elem)
                if record['title'] and (min_year is None or (record['year'] or 0) >= min_year):
                    yield record
            root.clear()


def ingest(path, store, *, accept, release, min_year=2008, progress_every=500_000):
    """Add records for which accept(record) is truthy. Returns counters."""
    started, seen, kept, new = time.time(), 0, 0, 0
    for record in iter_records(path, min_year=min_year):
        seen += 1
        decision = accept(record)
        if decision:
            kept += 1
            record['dblp_release'] = release
            _, is_new = store.add(record, origin=f'dblp:{release}')
            new += is_new
        if progress_every and seen % progress_every == 0:
            print(f'dblp: {seen:,} records read, {kept:,} kept, {new:,} new works, {time.time() - started:.0f}s', flush=True)
    store.set_mark('dblp_release', release)
    return {'records_read': seen, 'kept': kept, 'new_works': new, 'seconds': round(time.time() - started)}
