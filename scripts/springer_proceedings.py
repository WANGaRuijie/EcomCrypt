"""Collect public Springer book TOCs, keeping retrieval separate from editorial review."""
import re
from html import unescape
from urllib.parse import urljoin, urlsplit, urlunsplit
from datetime import datetime, timezone
from directory import write_json


def clean(text):
    return ' '.join(unescape(re.sub(r'<[^>]+>', ' ', text)).split())


def parse_toc(html, book_url):
    expected = re.search(r'Table of contents\s*\((\d+) papers\)', html)
    if not expected:
        raise ValueError('Missing publisher TOC count; do not count challenge pages as coverage')
    rows = []
    for block in re.findall(r'<li\b[^>]*data-test="chapter"[^>]*>(.*?)</li>', html, re.S):
        match = re.search(r'<a\b[^>]*href="(/chapter/10\.1007/[^"?#]+)"[^>]*>(.*?)</a>', block, re.S)
        if not match:
            continue  # Front/back matter has no research chapter link.
        url = urljoin(book_url, unescape(match[1]))
        pages = re.search(r'Pages\s+([0-9]+[-–][0-9]+)', clean(block))
        rows.append({'source': 'publisher', 'source_id': url, 'source_url': url,
                     'doi': url.split('/chapter/', 1)[1].lower(), 'title': clean(match[2]),
                     'authors': [], 'year': None, 'pages': pages[1] if pages else None,
                     'kind': 'conference-paper', 'url': url, 'abstract': '',
                     'editorial_review_required': True,
                     'review_status': 'toc_nomination_byline_date_and_contribution_pending'})
    next_url = None
    for anchor in re.findall(r'<a\b[^>]*>', html):
        if re.search(r'\brel="next"', anchor):
            href = re.search(r'\bhref="([^"]+)"', anchor)
            if href:
                joined = urlsplit(urljoin(book_url, unescape(href[1])))
                next_url = urlunsplit(joined._replace(fragment=''))
                if joined.netloc != urlsplit(book_url).netloc or joined.path != urlsplit(book_url).path:
                    raise ValueError('Publisher pagination left configured book')
    return rows, int(expected[1]), next_url


def scan_book(book, fetch, max_pages=4):
    url = book['url']; cursor = url; seen = set(); records = {}; checked = []; expected = None
    result = {'url': url, 'venue': book['venue'], 'event_year': book['event_year'],
              'part': book['part'], 'track': book['track'], 'complete': False,
              'coverage_stage': 'public_toc_retrieval_only', 'next_cursor': cursor}
    try:
        while cursor and len(checked) < max_pages:
            if cursor in seen:
                raise ValueError('Repeated publisher pagination cursor')
            seen.add(cursor)
            rows, count, next_url = parse_toc(fetch(cursor), url)
            if expected is not None and expected != count:
                raise ValueError('TOC count changed across pages')
            expected = count; checked.append(cursor)
            for row in rows:
                row.update(venue=book['venue'], event_year=book['event_year'],
                           proceedings_part=book['part'], proceedings_track=book['track'],
                           original_discovery={'book_url': url, 'toc_page': cursor})
                records[row['doi']] = row
            cursor = next_url
            result['next_cursor'] = cursor
        result.update(status='ok' if not cursor and len(records) == expected else 'incomplete',
                      complete=not cursor and len(records) == expected)
    except Exception as exc:
        result.update(status='unavailable', reason=type(exc).__name__, next_cursor=cursor)
    result.update(pages_checked=checked, records=len(records), expected_records=expected,
                  chapter_metadata_verified=0, contribution_reviews=0, adopted=0)
    return list(records.values()), result


def collect(books, fetch, output):
    records = []; coverage = []
    for book in books:
        rows, status = scan_book(book, fetch)
        records.extend(rows); coverage.append(status)
        print({k: status[k] for k in ('venue', 'event_year', 'part', 'status', 'records', 'complete')}, flush=True)
        write_json(output, {'retrieved_at': datetime.now(timezone.utc).isoformat(),
                            'records': records, 'coverage': coverage,
                            'policy': 'TOC nominations only; not primary contribution reviews or automatic publication upgrades.'})
    return records, coverage
