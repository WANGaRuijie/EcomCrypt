"""Source adapters and conservative bibliographic reconciliation."""

import hashlib
import html
import json
import os
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen


OPENALEX_FIELDS = (
    "id,doi,title,publication_year,primary_location,locations,type,authorships,is_retracted"
)
CROSSREF_FIELDS = (
    "DOI,title,author,container-title,published,published-print,published-online,"
    "issued,URL,type,relation,event"
)
SOURCES = ("openalex", "dblp", "crossref")
ENDPOINTS = {
    "openalex": "https://api.openalex.org/works",
    "dblp": "https://dblp.org/search/publ/api",
    "crossref": "https://api.crossref.org/works",
}
MIN_INTERVAL = {"openalex": 0.2, "dblp": 1.0, "crossref": 0.4}
NON_ARCHIVAL = {"preprint", "posted-content", "report", "report-series", "working-paper"}
VERSION_RELATIONS = {"is-preprint-of", "has-preprint", "is-version-of", "has-version"}


class MetadataError(RuntimeError):
    """A provider could not return usable data. Error messages omit secrets."""


def normalize_title(value):
    if not isinstance(value, str):
        return ""
    expanded = unicodedata.normalize("NFKD", html.unescape(value).casefold())
    unaccented = "".join(c for c in expanded if not unicodedata.combining(c))
    unaccented = re.sub(r"['’]", "", unaccented)
    return " ".join(re.findall(r"[^\W_]+", unaccented))


def normalize_doi(value):
    if not isinstance(value, str):
        return None
    cleaned = unquote(value.strip()).lower()
    cleaned = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", cleaned)
    return cleaned if re.fullmatch(r"10\.\d{4,9}/[^\s<>?#]+", cleaned) else None


def _doi_url(doi):
    return "https://doi.org/" + quote(doi, safe="/:")


def _url(value):
    if not isinstance(value, str):
        return None
    try:
        parts = urlsplit(value)
        if parts.scheme in {"https", "http"} and parts.hostname and not parts.username:
            return value
    except ValueError:
        pass
    return None


def _provider_id(value, pattern):
    if not isinstance(value, str):
        return None
    match = re.fullmatch(pattern, value)
    return match.group(1) if match else None


def _orcid(value):
    return _provider_id(value, r"(?:https?://orcid\.org/)?(\d{4}-\d{4}-\d{4}-\d{3}[\dX])")


def _ror(value):
    return _provider_id(value, r"(?:https?://ror\.org/)?(0[a-z0-9]{8})")


def _openalex_id(value, prefix):
    return _provider_id(value, rf"(?:https?://openalex\.org/)?({prefix}\d+)")


def _nonempty_ids(**values):
    return {key: value for key, value in values.items() if value}


def _text(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def _year(value):
    if isinstance(value, str) and re.fullmatch(r"\d{4}", value):
        value = int(value)
    return value if type(value) is int and 1000 <= value <= 2100 else None


def _items(value):
    return value if isinstance(value, list) else []


def _dict(value):
    return value if isinstance(value, dict) else {}


def _first_text(values):
    return next((value for raw in _items(values) if (value := _text(raw))), None)


def _authors_complete(authors):
    return bool(authors) and all(_text(author.get("name")) for author in authors)


def _author(name, ids=None, institutions=None):
    return {"name": name, "ids": ids or {}, "institutions": institutions or []}


def _openalex_author(authorship):
    person = _dict(authorship.get("author"))
    institutions = [
        {
            "name": institution["display_name"],
            "ids": _nonempty_ids(
                openalex=_openalex_id(institution.get("id"), "I"), ror=_ror(institution.get("ror"))
            ),
        }
        for institution in _items(authorship.get("institutions"))
        if isinstance(institution, dict) and _text(institution.get("display_name"))
    ]
    return _author(
        _text(person.get("display_name")) or _text(authorship.get("raw_author_name")),
        _nonempty_ids(
            openalex=_openalex_id(person.get("id"), "A"), orcid=_orcid(person.get("orcid"))
        ),
        institutions,
    )


def _openalex_record(raw):
    identifier = _openalex_id(raw.get("id"), "W")
    source_url = f"https://openalex.org/{identifier}" if identifier else None
    primary = _dict(raw.get("primary_location"))
    source = _dict(primary.get("source"))
    doi = normalize_doi(raw.get("doi"))
    locations = [loc for loc in _items(raw.get("locations")) if isinstance(loc, dict)]
    location_source = next(
        (
            _dict(location.get("source"))
            for location in locations
            if doi and normalize_doi(location.get("landing_page_url")) == doi
            and _text(_dict(location.get("source")).get("display_name"))
        ),
        {},
    )
    related_dois = {
        found
        for location in locations
        if location.get("version") in {"submittedVersion", "acceptedVersion", "publishedVersion"}
        and (found := normalize_doi(location.get("landing_page_url"))) and found != doi
    }
    kind = _text(raw.get("type"))
    if source.get("type") == "repository" and primary.get("version") == "submittedVersion":
        kind = "preprint"
    venue = _text(source.get("display_name"))
    if doi and doi.startswith("10.48550/arxiv."):
        venue = _text(location_source.get("display_name")) or venue
        kind = "preprint"
    return {
        "source": "openalex",
        "source_id": identifier,
        "source_url": source_url,
        "title": _text(raw.get("title")) or _text(raw.get("display_name")),
        "year": _year(raw.get("publication_year")),
        "doi": doi,
        "venue": venue,
        "primary_location_venue": _text(source.get("display_name")),
        "authors": [_openalex_author(a) for a in _items(raw.get("authorships")) if isinstance(a, dict)],
        "url": _doi_url(doi) if doi else _url(primary.get("landing_page_url")) or source_url,
        "kind": kind,
        "related_dois": sorted(related_dois),
        "is_retracted": raw.get("is_retracted") if type(raw.get("is_retracted")) is bool else None,
        **({'abstract': ' '.join(word for _, word in sorted(
            (position, word) for word, positions in (raw.get('abstract_inverted_index') or {}).items()
            for position in positions))} if 'abstract_inverted_index' in raw else {}),
    }


def _dblp_author(raw):
    if isinstance(raw, str):
        return _author(_text(raw))
    name = _text(raw.get("text"))
    return _author(
        re.sub(r" \d{4}$", "", name) if name else None,
        _nonempty_ids(dblp=_text(raw.get("@pid"))),
    )


def _dblp_record(raw):
    identifier = _text(raw.get("key"))
    source_url = _url(raw.get("url")) or (
        f"https://dblp.org/rec/{quote(identifier)}" if identifier else None
    )
    author_values = _dict(raw.get("authors")).get("author", [])
    if not isinstance(author_values, list):
        author_values = [author_values]
    doi = normalize_doi(raw.get("doi")) or normalize_doi(raw.get("ee"))
    return {
        "source": "dblp",
        "source_id": identifier,
        "source_url": source_url,
        "title": _text(raw.get("title")),
        "year": _year(raw.get("year")),
        "doi": doi,
        "venue": _text(raw.get("venue")),
        "authors": [_dblp_author(a) for a in author_values if isinstance(a, (str, dict))],
        "url": _doi_url(doi) if doi else _url(raw.get("ee")) or source_url,
        "kind": {
            "Informal and Other Publications": "preprint",
            "Conference and Workshop Papers": "proceedings-article",
            "Journal Articles": "journal-article",
        }.get(raw.get("type"), _text(raw.get("type"))),
        "related_dois": [],
        "is_retracted": None,
    }


def _crossref_author(raw):
    name = " ".join(v for k in ("given", "family") if (v := _text(raw.get(k))))
    institutions = []
    for affiliation in _items(raw.get("affiliation")):
        if not isinstance(affiliation, dict) or not _text(affiliation.get("name")):
            continue
        ror = next(
            (
                candidate
                for entity in _items(affiliation.get("id"))
                if isinstance(entity, dict) and (candidate := _ror(entity.get("id")))
            ),
            None,
        )
        institutions.append({"name": affiliation["name"], "ids": _nonempty_ids(ror=ror)})
    return _author(name or _text(raw.get("name")), _nonempty_ids(orcid=_orcid(raw.get("ORCID"))), institutions)


def _crossref_year(raw):
    # Print/issue and online publication can occur in different years. Preserve both.
    dates = {}
    for field in ("published-print", "published", "published-online", "issued"):
        parts = _items(_dict(raw.get(field)).get("date-parts"))
        if parts and isinstance(parts[0], list) and parts[0] and (year := _year(parts[0][0])):
            dates[field] = year
    return next(iter(dates.values()), None), dates


def _crossref_record(raw):
    doi = normalize_doi(raw.get("DOI"))
    year, year_fields = _crossref_year(raw)
    kind = _text(raw.get("type"))
    event_name = _text(_dict(raw.get("event")).get("name"))
    container = _first_text(raw.get("container-title"))
    if kind in {"book-chapter", "proceedings-article"}:
        containers = [_text(value) for value in _items(raw.get("container-title"))]
        container = next((value for value in containers if value and value not in {
            "Lecture Notes in Computer Science", "Lecture Notes in Artificial Intelligence",
            "Communications in Computer and Information Science",
        }), container)
    relations = _dict(raw.get("relation"))
    related_dois = {
        found
        for key in VERSION_RELATIONS
        for relation in _items(relations.get(key))
        if isinstance(relation, dict) and relation.get("id-type") == "doi"
        and (found := normalize_doi(relation.get("id"))) and found != doi
    }
    return {
        "source": "crossref",
        "source_id": doi,
        "source_url": f"{ENDPOINTS['crossref']}/{quote(doi, safe='/')}" if doi else None,
        "title": " ".join(re.sub(r"<[^>]+>", " ", _first_text(raw.get("title")) or "").split()),   # Crossref keeps JATS markup such as <scp>
        "year": year,
        "year_fields": year_fields,
        "doi": doi,
        "venue": (event_name or container) if kind in {"book-chapter", "proceedings-article"} else (container or event_name),
        "authors": [
            _crossref_author(author) for author in _items(raw.get("author")) if isinstance(author, dict)
        ],
        "url": _doi_url(doi) if doi else _url(raw.get("URL")),
        "kind": kind,
        "related_dois": sorted(related_dois),
        "is_retracted": None,
    }


def seed_queries(title):
    phrase = title.replace('"', '')
    return {
        "openalex": {"search": f'"{phrase}"', "per_page": 5, "select": OPENALEX_FIELDS},
        "dblp": {"q": normalize_title(title), "h": 8, "format": "json"},
        "crossref": {"query.bibliographic": title, "rows": 6, "select": CROSSREF_FIELDS},
    }


def public_query_url(source, params):
    safe = {key: value for key, value in params.items() if key not in {"api_key", "mailto"}}
    endpoint = ENDPOINTS[source]
    if source == "crossref" and "doi" in safe:
        endpoint += "/" + quote(safe.pop("doi"), safe="/")
    return f"{endpoint}?{urlencode(sorted(safe.items()))}" if safe else endpoint


def cache_path(cache_dir, url):
    return Path(cache_dir) / (hashlib.sha256(url.encode("utf-8")).hexdigest() + ".json")


def _cache_write(path, envelope):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temp_path = Path(stream.name)
            json.dump(envelope, stream, ensure_ascii=False)
        temp_path.replace(path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


class MetadataClient:
    """Read only public metadata, with cache-first requests and an offline mode."""

    def __init__(self, cache_dir, *, offline=False, refresh=False, contact=None, openalex_key=None):
        self.cache_dir = Path(cache_dir)
        self.offline = offline
        self.refresh = refresh
        self.contact = contact or os.environ.get("CROSSREF_MAILTO")
        self.openalex_key = openalex_key or os.environ.get("OPENALEX_API_KEY")
        self._locks = {source: Lock() for source in SOURCES}
        self._last_request = dict.fromkeys(SOURCES, 0.0)
        self._blocked_sources = set()
        shared_cache = Path(__file__).resolve().parents[1]/'.cache'
        self.backoff_dir = (shared_cache if self.cache_dir.resolve().is_relative_to(shared_cache)
                            else self.cache_dir)/'source-backoff'

    def _fetch(self, source, params):
        url = public_query_url(source, params)
        path = cache_path(self.cache_dir, url)
        if path.exists() and (self.offline or not self.refresh):
            try:
                envelope = json.loads(path.read_text(encoding="utf-8"))
                if envelope.get("url") == url and isinstance(envelope.get("payload"), dict):
                    return envelope
            except (AttributeError, OSError, ValueError):
                pass
            if self.offline:
                raise MetadataError("invalid_cache")
        if self.offline:
            raise MetadataError("offline_cache_miss")
        try:
            cooldown=json.loads((self.backoff_dir/f'{source}.json').read_text(encoding='utf-8'))
            if cooldown['retry_after_epoch'] > time.time():
                raise MetadataError('http_429_source_backoff')
        except (OSError,ValueError,KeyError,TypeError):
            pass
        # A non-JSON DBLP response often means an anti-bot page. Reuse valid
        # cache entries above, but do not retry different queries every batch.
        if source == 'dblp':
            try:
                cooldown = json.loads((self.cache_dir / 'dblp-backoff.json').read_text(encoding='utf-8'))
                if cooldown['retry_after_epoch'] > time.time():
                    raise MetadataError('invalid_json_source_backoff')
            except (OSError, ValueError, KeyError, TypeError):
                pass
        credentials = {}
        if source == "openalex" and self.openalex_key:
            credentials["api_key"] = self.openalex_key
        if source == "crossref" and self.contact:
            credentials["mailto"] = self.contact
        separator = "&" if "?" in url else "?"
        request_url = f"{url}{separator}{urlencode(credentials)}" if credentials else url
        agent = "EconCS-Scholar-Directory/1.0"
        if source == "crossref" and self.contact:
            agent += f" (mailto:{self.contact})"
        request = Request(request_url, headers={"Accept": "application/json", "User-Agent": agent})
        payload = self._download(source, request)
        envelope = {
            "url": url,
            "retrieved_at": datetime.now(timezone.utc).date().isoformat(),
            "payload": payload,
        }
        # Validate the envelope before caching so a provider error can be retried.
        _records(source, payload)
        _cache_write(path, envelope)
        return envelope

    def _download(self, source, request):
        with self._locks[source]:
            if source in self._blocked_sources:
                raise MetadataError('http_429_session_backoff')
            wait = self._last_request[source] + MIN_INTERVAL[source] - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_request[source] = time.monotonic()
            try:
                with urlopen(request, timeout=8) as response:
                    contents = response.read(4 * 1024 * 1024 + 1)
            except HTTPError as exc:
                code = exc.code
                retry_after=exc.headers.get('Retry-After') if exc.headers else None
                exc.close()
                if code == 429:
                    self._blocked_sources.add(source)
                    try:
                        delay=float(retry_after)
                    except (ValueError,TypeError):
                        try:delay=parsedate_to_datetime(retry_after).timestamp()-time.time()
                        except (ValueError,TypeError,AttributeError,OverflowError):delay=3600
                    _cache_write(self.backoff_dir/f'{source}.json',{
                        'reason':'http_429','retry_after_epoch':time.time()+max(60,delay),
                        'policy':'Honor provider Retry-After; otherwise one hour. Cached data remain usable.'})
                raise MetadataError(f"http_{code}") from None
            except (OSError, URLError):
                raise MetadataError("network_error") from None
        if len(contents) > 4 * 1024 * 1024:
            raise MetadataError("response_too_large")
        try:
            payload = json.loads(contents)
        except (UnicodeError, ValueError):
            if source == 'dblp':
                _cache_write(self.cache_dir / 'dblp-backoff.json', {
                    'source': 'dblp', 'reason': 'invalid_json',
                    'retry_after_epoch': time.time() + 3600,
                })
            raise MetadataError("invalid_json") from None
        if not isinstance(payload, dict):
            raise MetadataError("unexpected_response")
        return payload

    def _query(self, source, params):
        envelope = self._fetch(source, params)
        records = _records(source, envelope["payload"])
        for record in records:
            record["retrieved_at"] = envelope.get("retrieved_at")
            record["query_url"] = envelope["url"]
        return records, envelope.get("retrieved_at")

    def _search(self, source, params):
        return self._query(source, params)[0]

    def search_openalex(self, params):
        return self._search("openalex", {"select": OPENALEX_FIELDS, **params})

    def lookup_crossref(self, doi):
        doi = normalize_doi(doi)
        if doi is None:
            raise ValueError("invalid DOI")
        return self._search("crossref", {"doi": doi})

    def verify(self, seed, *, observed=()):
        requests = seed_queries(seed["title"])
        queries = []
        records = list(observed)
        with ThreadPoolExecutor(max_workers=len(SOURCES)) as executor:
            pending = {
                source: executor.submit(self._query, source, params)
                for source, params in requests.items()
            }
            for source in SOURCES:
                query = {"source": source, "url": public_query_url(source, requests[source])}
                try:
                    results, retrieved_at = pending[source].result()
                except MetadataError as exc:
                    query.update(status="unavailable", reason=str(exc))
                else:
                    query.update(status="ok", records=len(results), retrieved_at=retrieved_at)
                    records.extend(results)
                queries.append(query)
        registered = {record["doi"] for record in records if record["source"] == "crossref"}
        candidate_dois = list(dict.fromkeys(
            record["doi"] for record in records
            if record["doi"] and record["doi"] not in registered
            and not record["doi"].startswith("10.48550/arxiv.")
            and _title_match(seed, record) and _seed_authors_match(seed.get("authors"), record["authors"])
        ))
        for doi in candidate_dois[:4]:
            params = {"doi": doi}
            query = {"source": "crossref", "url": public_query_url("crossref", params)}
            try:
                results, retrieved_at = self._query("crossref", params)
            except MetadataError as exc:
                query.update(status="unavailable", reason=str(exc))
            else:
                query.update(status="ok", records=len(results), retrieved_at=retrieved_at)
                records.extend(results)
            queries.append(query)
        unique_records = {(record["source"], record["source_id"]): record for record in records}
        return {**reconcile(seed, unique_records.values()), "queries": queries}


def _records(source, payload):
    if source == "openalex":
        values, parse = payload.get("results"), _openalex_record
    elif source == "crossref":
        message = _dict(payload.get("message"))
        values = [message] if normalize_doi(message.get("DOI")) else message.get("items")
        parse = _crossref_record
    else:
        hits = _dict(_dict(payload.get("result")).get("hits"))
        values = hits.get("hit")
        if values is None and str(hits.get("@total")) == "0":
            values = []
        if isinstance(values, list):
            values = [_dict(hit).get("info") for hit in values]
        parse = _dblp_record
    if not isinstance(values, list) or any(not isinstance(value, dict) for value in values):
        raise MetadataError("unexpected_response")
    return [record for value in values if (record := parse(value))["title"] and record["source_id"]]


PERSON_LETTERS = str.maketrans({
    "ı": "i", "ł": "l", "Ł": "l", "ø": "o", "Ø": "o", "đ": "d", "Đ": "d", "ß": "ss", "æ": "ae", "œ": "oe",
    "‐": "-", "‑": "-",
})


def _person_tokens(name):
    name = re.sub(r" \d{4}$", "", name or "").translate(PERSON_LETTERS)
    if name.count(",") == 1:                    # "Han, Chunghyun"
        family, given = name.split(",")
        name = f"{given} {family}"
    return normalize_title(name).split()


def _same_person(left, right):
    # Matching IDs settle it. Differing IDs do not: indexes often attach the wrong ORCID to the right name.
    shared = left.get("ids", {}).keys() & right.get("ids", {}).keys()
    if shared and all(left["ids"][key] == right["ids"][key] for key in shared):
        return True
    a, b = _person_tokens(left.get("name")), _person_tokens(right.get("name"))
    if not a or not b:
        return False
    if a == b or "".join(a) == "".join(b) or sorted(a) == sorted(b):      # "Sheng-Nan Li", "Lu Yun" / "Yun Lu"
        return True
    if min(len(a), len(b)) >= 2 and (set(a) <= set(b) or set(b) <= set(a)):   # "Brett Hemenway" / "Brett Hemenway Falk"
        return True
    if a[-1] != b[-1]:
        return False
    if len(a) < 2 or len(b) < 2:
        return False
    # Full given names must match, or one must be an initial. Optional middle
    # initials may be missing from a publisher deposit.
    given_matches = a[0] == b[0] or (min(len(a[0]), len(b[0])) == 1 and a[0][0] == b[0][0])
    return given_matches and all(
        x == y or (min(len(x), len(y)) == 1 and x[0] == y[0])
        for x, y in zip(a[1:-1], b[1:-1])
    )


def _same_authors(left, right):
    return (
        _authors_complete(left) and _authors_complete(right) and len(left) == len(right)
        and all(_same_person(a, b) for a, b in zip(left, right))
    )


def _seed_authors_match(seed_authors, authors):
    if not seed_authors:
        return True
    if not _authors_complete(authors) or len(seed_authors) != len(authors):
        return False
    for hint, author in zip(seed_authors, authors):
        tokens = _person_tokens(hint if isinstance(hint, str) else hint.get("name"))
        actual = _person_tokens(author["name"])
        if tokens and actual[-len(tokens):] == tokens:
            continue
        if not _same_person(_author(" ".join(tokens)), author):
            return False
    return True


def _similar_byline(left, right):
    """Most family names agree; tolerates one dropped author or an affiliation parsed as an author."""
    a, b = [{tokens[-1] for author in byline or [] if (tokens := _person_tokens(author.get("name")))} for byline in (left, right)]
    return bool(a and b) and len(a & b) / max(len(a), len(b)) >= 0.6


def _nonarchival(record):
    doi = record.get("doi") or ""
    return record.get("kind") in NON_ARCHIVAL or doi.startswith(("10.2139/ssrn.", "10.48550/arxiv."))


VENUE_ALIASES = {
    "aft": "advances in financial technologies",
    "ec": "electronic commerce|economics and computation",
    "fc": "financial cryptography",
    "focs": "foundations of computer science",
    "nber wp": "national bureau of economic research",
    "nsdi": "networked systems design and implementation",
    "podc": "principles of distributed computing",
    "res": "review of economic studies",
    "rfs": "review of financial studies",
    "s p": "symposium on security and privacy",
    "soda": "discrete algorithms",
    "stoc": "theory of computing",
    "www": "world wide web",
}


def _venue_match(hint, value):
    hint = normalize_title(hint)
    value = normalize_title(value)
    if not hint or not value:
        return False
    aliases = [hint, *VENUE_ALIASES.get(hint, "").split("|")]
    return any(alias and f" {alias} " in f" {value} " for alias in aliases)


def _main_title(value):
    return normalize_title(re.split(r":| [–—-] ", value, maxsplit=1)[0])


def _title_match(seed, record):
    title = record.get("title") or ""
    key = normalize_title(title)
    aliases = [seed["title"], *seed.get("title_aliases", [])]
    if key and any(key == normalize_title(alias) for alias in aliases):
        return "exact_title"
    # The record the seed's own DOI resolves to is the same work even when the title changed between the working
    # paper and the journal version (OpenAlex often pairs the SSRN title with the journal DOI).
    if (seed.get("doi") and normalize_doi(record.get("doi")) == normalize_doi(seed["doi"])
            and seed.get("authors") and _seed_authors_match(seed["authors"], record.get("authors", []))):
        return "same_doi"
    # Hyphenation and spacing only: "Un-Tethered" / "Untethered", "Block chain" / "Blockchain".
    if key and len(key) >= 8 and any(key.replace(" ", "") == normalize_title(alias).replace(" ", "") for alias in aliases):
        return "exact_title"
    # A shortened conference title is admissible when the complete ordered
    # byline, edition year and venue also match the input citation.
    full = normalize_title(seed["title"])
    main = _main_title(seed["title"])
    if (
        seed.get("authors") and len(main) >= 8 and len(key) >= 8 and main == _main_title(title)
        and key != full and (main == key or main == full)
        and _year(seed.get("year")) == record.get("year")
        and _venue_match(seed.get("venue"), record.get("venue"))
        and _seed_authors_match(seed["authors"], record.get("authors", []))
    ):
        return "seed_venue_year_title_variant"
    return None


def _equal_edition(left, right):
    if left.get("doi") and right.get("doi"):
        return left["doi"] == right["doi"]
    if left.get("source") == right.get("source") and left.get("source_id") == right.get("source_id"):
        return True
    return (
        normalize_title(left["title"]) == normalize_title(right["title"])
        and left.get("year") is not None and left.get("year") == right.get("year")
        and (
            _nonarchival(left) == _nonarchival(right)
            or (not left.get("doi") and not left.get("venue"))
            or (not right.get("doi") and not right.get("venue"))
        )
        and (
            left.get("source") != right.get("source")
            or not (left.get("venue") and right.get("venue"))
        )
        and _same_authors(left.get("authors", []), right.get("authors", []))
    )


def _edition_groups(records):
    groups = []
    # Group records with DOIs first. DOI-free records can attach to one unique
    # edition, but cannot bridge distinct DOIs through a transitive match.
    for record in sorted(records, key=lambda row: not row.get("doi")):
        matches = [group for group in groups if all(_equal_edition(record, peer) for peer in group)]
        if len(matches) == 1:
            matches[0].append(record)
        else:
            groups.append([record])
    return groups


def _related_editions(left, right):
    for a in left:
        for b in right:
            if a.get("doi") in b.get("related_dois", []) or b.get("doi") in a.get("related_dois", []):
                return True
            titles = (normalize_title(a["title"]), normalize_title(b["title"]))
            same_title = titles[0] == titles[1]
            distinct_subtitle = (
                _main_title(a["title"]) == _main_title(b["title"])
                and _main_title(a["title"]) in titles
                and min(map(len, titles)) >= 8
            )
            if (
                _nonarchival(a) != _nonarchival(b)
                and (same_title or distinct_subtitle)
                and _same_authors(a.get("authors", []), b.get("authors", []))
                and a.get("year") and b.get("year")
            ):
                earlier, later = (a, b) if _nonarchival(a) else (b, a)
                if 0 <= later["year"] - earlier["year"] <= 5:
                    return True
    return False


def _merge_author(target, value, record, include_affiliation):
    target["ids"].update(value.get("ids", {}))
    for institution in value.get("institutions", []) if include_affiliation else []:
        observation = {
            **institution,
            "source": record["source"],
            "source_id": record["source_id"],
            "year": record.get("year"),
        }
        if observation not in target["institutions"]:
            target["institutions"].append(observation)


def _resolve_edition(records, seed):
    priority = {"publisher": 0, "crossref": 1, "dblp": 2, "openalex": 3}
    ordered = sorted(
        records,
        key=lambda row: (
            priority.get(row["source"], 4), not row.get("doi"), not row.get("venue"), row["source_id"]
        ),
    )
    source_ids = {}
    conflicts = []
    for record in ordered:
        source_ids.setdefault(record["source"], record["source_id"])
    authors = []
    archival = any(not _nonarchival(record) for record in ordered)
    for record in ordered:
        byline = record.get("authors", [])
        if not _authors_complete(byline):
            continue
        if not authors:
            authors = [_author(author["name"]) for author in byline]
        if len(authors) != len(byline):
            conflicts.append({"field": "authors", "reason": "source_disagreement"})
            continue
        for target, author in zip(authors, byline):
            if _same_person(target, author):
                _merge_author(target, author, record, not archival or not _nonarchival(record))
            elif {"field": "authors", "reason": "source_disagreement"} not in conflicts:
                conflicts.append({"field": "authors", "reason": "source_disagreement"})

    year = next((r["year"] for r in ordered if r.get("year")), None)
    source_years = {r["year"] for r in ordered if r.get("year")}
    dates = {value for r in ordered for value in r.get("year_fields", {}).values()}
    hint_year = _year(seed.get("year"))
    publisher_year = next(
        (record["year"] for record in ordered if record["source"] == "publisher" and record.get("year")),
        None,
    )
    if publisher_year:
        year = publisher_year
    elif hint_year in dates:
        year = hint_year
    if len(source_years) > 1 and not source_years <= dates:
        registrar_years = {r["year"] for r in ordered if r.get("year") and r["source"] != "openalex"}
        if len(registrar_years) == 1 or max(source_years) - min(source_years) == 1:
            # One edition (records here share a DOI): OpenAlex keeps the first preprint's year, and online-first,
            # in-issue and conference years differ by one. DBLP's year is the edition's own.
            year = publisher_year or next((r["year"] for r in ordered if r["source"] == "dblp" and r.get("year")), year)
        else:
            conflicts.append({"field": "year", "reason": "source_disagreement", "values": sorted(source_years)})
            if not publisher_year and year not in dates:
                year = None
    if hint_year and source_years and hint_year not in source_years | dates:
        conflicts.append({"field": "year", "reason": "seed_disagreement", "values": sorted(source_years)})
    doi = next((r["doi"] for r in ordered if r.get("doi")), None)
    venue_priority = {"publisher": 0, "dblp": 1, "crossref": 2, "openalex": 3}
    venue_order = sorted(
        records,
        key=lambda row: (
            _nonarchival(row),
            not _venue_match(seed.get("venue"), row.get("venue")),
            venue_priority.get(row["source"], 4),
            row["source_id"],
        ),
    )
    if any(r.get("is_retracted") is True for r in ordered):
        conflicts.append({"field": "is_retracted", "reason": "source_retraction"})
    metadata = {
        "title": ordered[0]["title"],
        "authors": authors,
        "year": year,
        "doi": doi,
        "venue": next((r["venue"] for r in venue_order if r.get("venue")), None),
        "url": _doi_url(doi) if doi else next((r["url"] for r in ordered if r.get("url")), None),
        "kind": next((r["kind"] for r in venue_order if r.get("kind")), None),
        "source_ids": source_ids,
        "is_retracted": next(
            (value for value in (True, False) if any(r.get("is_retracted") is value for r in ordered)),
            None,
        ),
    }
    return metadata, conflicts


def _prefer_edition(choices, seed_doi):
    """Pick among unlinked editions: the one the seed names, else the best-attested of several preprints."""
    named = [group for group in choices if seed_doi and any(record.get("doi") == seed_doi for record in group)]
    if len(named) == 1:
        return named
    if all(_nonarchival(record) for group in choices for record in group):
        return [max(choices, key=lambda group: (len({r["source"] for r in group}), any(r.get("doi") for r in group),
                                                 sorted(r["source_id"] for r in group)))]
    return choices


def reconcile(seed, records):
    """Verify a bibliographic edition while preserving candidate source records."""
    evidence = []
    candidates = []
    for record in records:
        match = _title_match(seed, record)
        if not match:
            continue
        if record.get("authors") and not _seed_authors_match(seed.get("authors"), record["authors"]):
            evidence.append({**record, "match": "seed_author_mismatch"})
            continue
        evidence.append({**record, "match": match})
        candidates.append(record)

    result = {"status": "unverified", "metadata": None, "evidence": evidence, "conflicts": [], "versions": []}
    if not candidates:
        return result

    groups = _edition_groups(candidates)
    hint_year = _year(seed.get("year"))
    def edition_years(group):
        return {r.get("year") for r in group} | {
            year for r in group for year in r.get("year_fields", {}).values()
        }

    year_matches = [
        group for group in groups if hint_year is not None and hint_year in edition_years(group)
    ]
    venue_matches = [
        group for group in (year_matches or groups)
        if any(_venue_match(seed.get("venue"), record.get("venue")) for record in group)
    ]
    choices = venue_matches or year_matches or groups
    archival = [group for group in choices if any(not _nonarchival(record) for record in group)]
    choices = archival or choices
    if len(choices) > 1:
        choices = _prefer_edition(choices, normalize_doi(seed.get("doi")))
    if len(choices) != 1:
        return {**result, "status": "ambiguous", "conflicts": [{"field": "edition", "reason": "multiple_unlinked_records"}]}
    primary = choices[0]
    if (
        not any(not _nonarchival(record) for record in primary)
        and hint_year and not any(abs(year - hint_year) <= 3 for year in edition_years(primary) if year)
    ):
        return {**result, "conflicts": [{"field": "edition", "reason": "only_distant_nonarchival_record"}]}

    metadata, conflicts = _resolve_edition(primary, seed)
    primary_doi = metadata["doi"]
    same_doi = [r for r in evidence if r["match"] == "seed_author_mismatch" and primary_doi and r.get("doi") == primary_doi]
    for record in same_doi:
        if _similar_byline(record.get("authors"), metadata["authors"]):
            metadata["source_ids"].setdefault(record["source"], record["source_id"])     # same DOI and title, noisy byline
        elif {"field": "authors", "reason": "seed_author_mismatch_on_same_doi"} not in conflicts:
            conflicts.append({"field": "authors", "reason": "seed_author_mismatch_on_same_doi"})
    versions = [
        _resolve_edition(group, {})[0]
        for group in groups if group is not primary and _related_editions(primary, group)
    ]
    # The same DOI can match two indexed sources even when one omits authors.
    # DBLP alone settles a formal CS publication: many proceedings (USENIX, older ACM/IEEE) have no second index entry.
    dblp_only = set(metadata["source_ids"]) == {"dblp"} and any(not _nonarchival(record) for record in primary)
    verified = (
        (len(metadata["source_ids"]) >= 2 or dblp_only)
        and metadata["year"] and metadata["venue"] and metadata["authors"] and not conflicts
    )
    return {
        **result,
        "status": "verified" if verified else "partial",
        "metadata": metadata,
        "conflicts": conflicts,
        "versions": versions,
    }
