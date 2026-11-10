"""Venue-level quality gate: deny / allow / preprint / unknown.

Decided once per venue (data/venue_policy_v2.json + data/venue_registry_v1.json),
never paper by paper. Scope screening is separate and always applies.
"""
import html
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from directory import read_json

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / 'data/venue_policy_v2.json'
REGISTRY = ROOT / 'data/venue_registry_v1.json'
TIERS = ROOT / 'data/venue_tiers_v1.json'
PREPRINT = re.compile(r'\b(arxiv|corr|ssrn|eprint|cryptol(?:ogy)? eprint|preprint|working paper|nber|cepr|repec)\b')
# Book-series names (OpenAlex often reports the series, not the conference) carry no
# venue information; the event is resolved later from Crossref/DBLP before any decision.
SERIES = re.compile(r'^(lecture notes (in|of|on)\b|communications in computer and information science|springer (ebooks|proceedings in)|'
                    r'advances in (intelligent systems and computing|information security)|studies in computational intelligence|'
                    r'smart innovation|lecture notes|ifip advances|elsevier ebooks|crc press ebooks|igi global ebooks)')

VOLUME = re.compile(r'\s*\(\s*(workshops?\s*)?[ab]?\d+\s*\)\s*$', re.IGNORECASE)     # DBLP: "CRYPTO (2)", "FC (Workshops 1)"
PARENS = re.compile(r'\s*\([^()]*\)')
SIDE_TRACK = re.compile(r'companion|workshop|poster|demo|supplement|abstract|doctoral|student|tutorial|track', re.IGNORECASE)
WRAPPER = re.compile(r'^(?:proceedings|of|the|in|annual|acm|ieee|usenix|siam|ifip|\d+(?:st|nd|rd|th)?|'
                     r'first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|\w+teenth|'
                     r'twentieth|thirtieth|fortieth|fiftieth|twenty|thirty|forty|fifty)$')
TAIL_WRAPPER = {'international', 'proceedings', 'part', 'volume', 'vol', 'i', 'ii', 'iii', 'iv'}
GENERIC_WORDS = {'international', 'conference', 'symposium', 'workshop', 'journal', 'annual', 'acm', 'ieee', 'on', 'of', 'the', 'and', 'in', 'for'}


def norm(text):
    return re.sub(r'[^a-z0-9]+', ' ', html.unescape(text or '').lower()).strip()


@lru_cache(maxsize=4)
def _load(policy_path=str(POLICY), registry_path=str(REGISTRY)):
    policy = read_json(policy_path)
    registry = read_json(registry_path)
    names = {}
    long_names = []
    for row in registry['venues']:
        for name in [row['name'], row['label'], *row.get('aliases', []), *row.get('dblp', [])]:
            key = norm(name)
            if key:
                names.setdefault(key, row)
                if len(key) > 15:
                    long_names.append((key, row))
    long_names.sort(key=lambda item: -len(item[0]))
    deny_names = {norm(v): rule for rule in policy['deny'] for v in rule.get('venues', [])}
    prefixes = [(p.lower(), rule) for rule in policy['deny'] for p in rule.get('doi_prefixes', [])]
    overrides = {o['doi'].lower(): o for o in policy.get('paper_overrides', []) if o.get('doi')}
    return names, long_names, deny_names, prefixes, overrides, policy.get('preprint_policy'), policy.get('non_english_venues')


def _non_english(value, rule):
    if any(unicodedata.category(ch).startswith('L') and not unicodedata.name(ch, '').startswith('LATIN') for ch in value):
        return True
    return bool(re.search(r'\b(?:' + '|'.join(rule['foreign_words']) + r')\b', value.lower()))


def clear_cache():
    _load.cache_clear()


def is_preprint(record):
    doi = (record.get('doi') or '').lower()
    venue = norm(record.get('venue') or record.get('dblp_venue'))
    return (record.get('kind') == 'preprint' or doi.startswith('10.48550/arxiv.')
            or record.get('source') in {'arxiv', 'iacr-eprint'} or bool(PREPRINT.search(venue)))


def _is_wrapper(token, row, tail):
    if WRAPPER.match(token) or token in norm(row['label']).split():
        return True
    return tail and token in TAIL_WRAPPER


def _wrapped(key, name, row):
    """True when the registered name is the whole string apart from proceedings wording, a year or the acronym."""
    at = f' {key} '.find(f' {name} ')
    if at < 0:
        return False
    head, tail = key[:max(at - 1, 0)].split(), key[at + len(name):].split()
    return all(_is_wrapper(t, row, False) for t in head) and all(_is_wrapper(t, row, True) for t in tail)


def _acronym_fits(outside, row):
    """A parenthetical acronym counts only if the surrounding words also describe that venue."""
    wanted = set(norm(row['name']).split()) - GENERIC_WORDS
    return bool(wanted) and len(wanted & set(norm(outside).split())) * 2 >= len(wanted)


def _registered(value, names, long_names):
    """Registry row for a venue string, or None. Substrings alone never match: 'European Journal of Finance' is not JF."""
    bare = VOLUME.sub(lambda m: ' workshops' if m[1] else '', value or '')
    for text in (bare, PARENS.sub(lambda m: m[0] if SIDE_TRACK.search(m[0]) else '', bare)):
        key = norm(text)
        row = names.get(key) or names.get(re.sub(r' \d{4}$', '', key))
        if row is None:
            row = next((r for name, r in long_names if _wrapped(key, name, r)), None)
        if row:
            return row
    for match in re.finditer(r'\(([^()]+)\)', bare):
        row = names.get(re.sub(r' \d{2,4}$', '', norm(match[1])))
        if row and not row.get('no_acronym_match') and _acronym_fits(bare.replace(match[0], ' '), row):
            return row
    return None


def venue_row(value):
    """Registry row for a venue as displayed, or None."""
    names, long_names, *_ = _load()
    return _registered(value, names, long_names) if norm(value) else None


@lru_cache(maxsize=1)
def _tiers():
    data = read_json(TIERS)
    return {label for labels in data['top'].values() for label in labels}, set(data['low']), set(data['deferred'])


def is_top(label):
    return label in _tiers()[0]


def queue_rank(venue):
    """Order for spending quota and LLM budget on waiting works: lower goes first, 9 is deferred."""
    top, low, deferred = _tiers()
    row = venue_row(venue)
    if not row:
        return 2
    label = row['label']
    if label in deferred:
        return 9
    if label in top:
        return 0
    if label in low:
        return 3
    return 2 if row['group'].startswith('Preprint') else 1


def _accepted_preprint(record, candidates, names, long_names, rule):
    """Only the channels in the registry (arXiv, IACR ePrint, SSRN, RePEc, working-paper series) count."""
    doi = (record.get('doi') or '').lower()
    return (record.get('source') in {'arxiv', 'iacr-eprint'}
            or any(doi.startswith(p) for p in rule.get('keep_doi_prefixes', []))
            or any(_registered(v, names, long_names) for v in candidates if norm(v)))


def classify(record, *, policy_path=POLICY, registry_path=REGISTRY):
    """Return {'decision', 'reason', 'venue_id'?, 'group'?} for one bibliographic record."""
    names, long_names, deny_names, prefixes, overrides, preprint_rule, language_rule = _load(str(policy_path), str(registry_path))
    doi = (record.get('doi') or '').lower()
    if doi in overrides:
        o = overrides[doi]
        return {'decision': o['decision'], 'reason': o.get('reason', 'paper override'), 'rule': 'paper_override'}
    for prefix, rule in prefixes:
        if doi.startswith(prefix):
            return {'decision': 'deny', 'reason': rule['reason'], 'rule': rule['id']}
    candidates = [record.get('accepted_venue'), record.get('venue'), record.get('dblp_venue')]
    for value in candidates:
        key = norm(value)
        if key and key in deny_names:
            rule = deny_names[key]
            return {'decision': 'deny', 'reason': rule['reason'], 'rule': rule['id']}
    if language_rule and any(v and _non_english(v, language_rule) and not _registered(v, names, long_names) for v in candidates):
        return {'decision': 'deny', 'reason': language_rule['reason'], 'rule': 'non-english-venue'}
    if is_preprint(record):
        if preprint_rule and not _accepted_preprint(record, candidates, names, long_names, preprint_rule):
            if not any(norm(v) for v in candidates):
                return {'decision': 'unresolved', 'reason': 'Preprint-typed record with no venue; resolve before deciding.'}
            return {'decision': 'deny', 'reason': preprint_rule['reason'], 'rule': 'preprint-channel'}
        return {'decision': 'preprint', 'reason': 'Preprint repository; shown as Preprint until a formal version is found.'}
    named = [v for v in candidates if norm(v) and not SERIES.search(norm(v))]
    if not named:
        return {'decision': 'unresolved', 'reason': 'Venue missing or only a book-series name; resolve the event before deciding.'}
    for value in named:
        row = _registered(value, names, long_names)
        if row is not None:
            return {'decision': 'allow', 'reason': 'Registered venue.', 'venue_id': row['id'], 'group': row['group']}
    return {'decision': 'unknown', 'reason': 'Venue not registered; decide once in venue_registry_v1.json or venue_policy_v2.json.'}


def work_denial(metadata, versions=()):
    """A work is removed only if its primary edition is denied and no other formal edition is acceptable."""
    primary = classify(metadata or {})
    if primary['decision'] != 'deny':
        return None
    for version in versions or []:
        verdict = classify(version)
        if verdict['decision'] in {'allow', 'unknown', 'unresolved'} and not is_preprint(version):
            return None
    return primary
