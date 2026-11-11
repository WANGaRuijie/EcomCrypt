"""Turn screened includes into verified ledger records (dry-run by default).

Gates, in order: screen decision/confidence -> venue policy on the best edition ->
editorial holds (quality_policy paper_overrides, editorial_scope_reviews) ->
bibliographic verification (OpenAlex + Crossref; the local DBLP dump record is
supplied as observed evidence, so dblp.org is never queried) -> venue policy on
the verified edition -> duplicate check against the current directory.
"""
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import rubric
import venue_policy
from build import EVIDENCE, LEDGER, OUTPUT, ROOT, SEEDS, project
from directory import is_formal_publication, read_json, write_json
from metadata import MetadataClient, MetadataError, _person_tokens, normalize_doi, normalize_title
from update import seed_from_record, verification_identity, work_identity

CONFIDENCE = {'low': 0, 'medium': 1, 'high': 2}
ARCHIVE_SOURCES = {'arxiv', 'iacr-eprint'}
EVIDENCE_SOURCES = ARCHIVE_SOURCES | {'dblp', 'openalex', 'crossref', 'publisher', 's2', 'scopus'}
# publisher: proceedings pages harvested locally (e.g. Dagstuhl LIPIcs). s2: Semantic Scholar records from the journal
# backfill, an independent index for title/authors/year; their venue is pinned from the Crossref ISSN, never S2's own.
# scopus: Scopus search hits from the ISSN backfill (an independent index; STANDARD view lists the first author only).
CROSSING_TOPIC = {'rational_crypto': 'rational-cryptography', 'security_econ': 'rational-cryptography',
                  'gt_systems': 'incentive-systems', 'governance': 'governance', 'crypto_finance': 'defi',
                  'blockchain_econ': 'economics', 'blockchain_mechanism': 'economics'}

TITLE_STOPWORDS = {'a', 'an', 'the', 'of', 'on', 'in', 'for', 'and', 'to', 'with', 'via', 'at', 'by', 'from', 'is', 'are', 'towards', 'toward'}
SOK = re.compile(r'^\s*sok\b|systemati[sz]ation of knowledge', re.IGNORECASE)


class LocalDblpClient(MetadataClient):
    """MetadataClient that never calls the dblp.org search API (the dump supplies DBLP evidence)."""

    def _query(self, source, params):
        if source == 'dblp':
            raise MetadataError('dblp_local_dump_used')
        return super()._query(source, params)


def best_edition(editions):
    def rank(e):
        verdict = venue_policy.classify(e)['decision']
        formal = not venue_policy.is_preprint(e)
        return ({'allow': 0, 'preprint': 1, 'unresolved': 2, 'unknown': 3, 'deny': 9}[verdict], not formal,
                {'openalex': 0, 'dblp': 1, 'arxiv': 2, 'iacr-eprint': 3}.get(e.get('source'), 5), e.get('source_id') or '')
    usable = [e for e in editions if e.get('title')]
    usable = [e for e in usable if e.get('year')] or usable      # reconstructed records carry no year and cannot be verified
    return sorted(usable, key=rank)[0] if usable else None


def archive_verification(record, indexed):
    """Unrefereed preprint verified from its official archive record (arXiv or IACR ePrint)."""
    locator = ('Official archive record; unrefereed preprint' if record['source'] in ARCHIVE_SOURCES
               else 'arXiv-minted DOI (10.48550) resolved through OpenAlex; unrefereed preprint')
    return {'status': 'verified',
            'metadata': {**{k: record.get(k) for k in ['title', 'authors', 'year', 'url', 'doi', 'venue', 'kind', 'is_retracted']},
                         'kind': 'preprint', 'source_ids': {record['source']: record['source_id']}},
            'evidence': [{'source': record['source'], 'source_url': record.get('source_url'), 'locator': locator}],
            'versions': [], 'conflicts': [], 'index_result': indexed,
            'verification_basis': 'primary_archive_metadata_not_peer_review'}


def _archive_record(record, editions):
    """The work's official archive record: an arXiv/ePrint edition, or an arXiv-DOI record from an index."""
    for edition in [record, *editions]:
        if edition.get('source') in ARCHIVE_SOURCES:
            return edition
    return record if (normalize_doi(record.get('doi')) or '').startswith('10.48550/arxiv.') else None


def verify(client, record, editions=()):
    # Every local edition is independent evidence; the DBLP dump in particular is never re-queried.
    observed = [record, *(e for e in editions if e is not record and e.get('source') in EVIDENCE_SOURCES and e.get('title'))]
    for doi in dict.fromkeys(d for d in (record.get('published_doi'), record.get('doi')) if d):
        if normalize_doi(doi) and normalize_doi(doi).startswith('10.48550/'):
            continue                      # arXiv DOIs are registered with DataCite, not Crossref
        try:
            observed.extend(client.lookup_crossref(doi))
        except (MetadataError, ValueError):
            pass
    query = seed_from_record(record)
    if record.get('kind') == 'preprint':
        query.pop('year', None)
        query.pop('venue', None)
    result = client.verify(query, observed=observed)
    archive = _archive_record(record, editions)
    if (archive and result['status'] in {'partial', 'unverified'}
            and not result['conflicts'] and not is_formal_publication(result.get('metadata') or {})
            and not archive.get('journal_ref') and not record.get('published_doi')):
        return archive_verification(archive, result)
    return result


def _edition_print(title, authors, year, preprint, label):
    names = [a.get('name') if isinstance(a, dict) else a for a in authors or []]
    return {'words': {w.rstrip('s') for w in normalize_title(title or '').split() if w not in TITLE_STOPWORDS},
            'families': {tokens[-1] for name in names if (tokens := _person_tokens(name))},
            'year': int(year) if str(year or '').isdigit() else None, 'preprint': preprint, 'label': label}


def _directory_prints(directory):
    prints = []
    for paper in directory['papers']:
        for edition in [paper, *paper.get('versions', [])]:
            prints.append(_edition_print(edition.get('title'), edition.get('authors') or paper.get('authors'), edition.get('year'),
                                         venue_policy.is_preprint(edition), paper['id'] + ' ' + (paper.get('title') or '')[:80]))
    return prints


def _same_work(a, b):
    # Preprint and published version under a changed title: most authors shared and most title words shared.
    if not (a['preprint'] or b['preprint']) or not a['families'] or not b['families']:
        return False                                    # two formal papers can legitimately coexist
    if a['year'] and b['year'] and abs(a['year'] - b['year']) > 4:
        return False
    if len(a['families'] & b['families']) / min(len(a['families']), len(b['families'])) < 0.6:
        return False
    shared = len(a['words'] & b['words'])
    if not shared or min(len(a['words']), len(b['words'])) < 3:
        return False
    return shared / len(a['words'] | b['words']) >= 0.6 or shared / min(len(a['words']), len(b['words'])) >= 0.85


def in_batch(item, batch):
    # Whether an accepted work belongs to the requested --apply batch. Preprint-only SoKs always wait for a human.
    metadata = item['record']['verification']['metadata']
    preprint = venue_policy.is_preprint(metadata)
    if batch.get('keys') is not None and item['key'] not in batch['keys']:
        return False
    if preprint and SOK.search(item['title']) and not item['screen'].get('editorial'):
        return False
    if batch.get('confidence') and item['screen'].get('confidence') != batch['confidence']:
        return False
    if batch.get('kind') and (batch['kind'] == 'preprint') != preprint:
        return False
    return not batch.get('groups') or venue_policy.classify(metadata).get('group') in batch['groups']


def _held(metadata, policy_overrides, scope_reviews):
    doi = normalize_doi(metadata.get('doi'))
    ids = metadata.get('source_ids') or {}
    for item in policy_overrides:
        if (item.get('doi') and normalize_doi(item['doi']) == doi) or any(ids.get(k) == v for k, v in (item.get('source_ids') or {}).items()):
            if item.get('decision') != 'adopt':
                return f"quality_policy hold: {item.get('reason', '')[:120]}"
    for item in scope_reviews:
        if item.get('decision') in {'exclude', 'review'} and (
                (doi and normalize_doi(item.get('doi')) == doi) or any(ids.get(k) == v for k, v in (item.get('source_ids') or {}).items())):
            return f"editorial_scope {item['decision']}: {item.get('reason', '')[:120]}"
    return None


def promote(store, config, *, apply=False, log=print, client=None, batch=None):
    version = rubric.version()
    minimum = CONFIDENCE[config['promotion']['min_confidence']]
    seeds, evidence = read_json(SEEDS), read_json(EVIDENCE)
    ledger = read_json(LEDGER) if LEDGER.exists() else {'schema_version': 1, 'records': []}
    directory = project(seeds, evidence, ledger)
    existing = set().union(*(work_identity(p) for p in directory['papers']))
    topics_known = set(rubric.topics())                 # ledger records keep the screening topics; display topics are applied at build
    quality = read_json(ROOT / 'data/quality_policy_v1.json').get('paper_overrides', [])
    scope_path = ROOT / 'data/editorial_scope_reviews_v1.json'
    scope_reviews = read_json(scope_path)['records'] if scope_path.exists() else []
    client = client or LocalDblpClient(ROOT / '.cache/metadata')

    chosen, outcome = [], {'accepted': [], 'held': [], 'review': [], 'duplicates': [], 'near_duplicates': [], 'failed': []}
    for work in store.works(['screen_include', 'review_metadata']):     # metadata failures are retried each run
        result, _ = store.screen(work['key'], 'abstract', version)
        if not result:
            continue
        if CONFIDENCE.get(result.get('confidence'), 0) < minimum:
            outcome['review'].append({'key': work['key'], 'title': work['title'], 'why': f"confidence {result.get('confidence')}", 'screen': result})
            store.set_status(work['key'], 'review_confidence', result.get('reason'))
            continue
        editions = store.editions(work['key'])
        edition = best_edition(editions)
        verdict = venue_policy.classify(edition or {})
        if edition is None or verdict['decision'] in {'deny', 'unknown'}:
            store.set_status(work['key'], 'denied_venue' if verdict['decision'] == 'deny' else 'venue_unknown', verdict['reason'])
            continue
        chosen.append((work, edition, result, editions))

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda item: _safe_verify(client, item[1], item[3]), chosen))

    def formal_first(pair):
        verified = pair[1]
        metadata = {} if isinstance(verified, Exception) else (verified.get('metadata') or {})
        return venue_policy.is_preprint(metadata), -CONFIDENCE.get(pair[0][2].get('confidence'), 0)

    prints = _directory_prints(directory)
    for (work, edition, screen, _), verified in sorted(zip(chosen, results), key=formal_first):
        row = {'key': work['key'], 'title': work['title'], 'venue': edition.get('venue'), 'screen': screen}
        if isinstance(verified, Exception) or verified.get('status') != 'verified' or verified.get('conflicts'):
            reason = str(verified) if isinstance(verified, Exception) else f"verification {verified.get('status')} {verified.get('conflicts') or ''}"
            outcome['failed'].append({**row, 'why': reason})
            store.set_status(work['key'], 'review_metadata', reason[:300])
            continue
        metadata = verified.get('metadata') or {}
        if not metadata.get('authors') or metadata.get('is_retracted') is True:
            outcome['failed'].append({**row, 'why': 'missing authors or retracted'})
            store.set_status(work['key'], 'review_metadata', 'missing authors or retracted')
            continue
        final = venue_policy.classify(metadata)
        if final['decision'] == 'deny':
            store.set_status(work['key'], 'denied_venue', final['reason'])
            continue
        if final['decision'] in {'unknown', 'unresolved'}:
            store.set_status(work['key'], 'venue_unknown', f"verified venue: {metadata.get('venue') or '-'}")
            continue
        hold = _held(metadata, quality, scope_reviews)
        if hold:
            outcome['held'].append({**row, 'why': hold})
            store.set_status(work['key'], 'held_editorial', hold)
            continue
        identities = verification_identity(verified)
        if identities & existing:
            outcome['duplicates'].append(row)
            store.set_status(work['key'], 'in_directory', 'verified edition already in directory')
            continue
        printed = _edition_print(metadata.get('title'), metadata.get('authors'), metadata.get('year'), venue_policy.is_preprint(metadata), work['title'][:80])
        twin = None if screen.get('editorial') else next((other for other in prints if _same_work(printed, other)), None)
        if twin:
            outcome['near_duplicates'].append({**row, 'twin': twin['label'], 'formal': not printed['preprint']})
            store.set_status(work['key'], 'held_editorial', f"near-duplicate of: {twin['label']}")
            continue
        prints.append(printed)
        topics = [t for t in screen.get('topics', []) if t in topics_known] or \
            [CROSSING_TOPIC.get(screen.get('crossing'), 'economics')]
        verified = deepcopy(verified)
        verified['scope_review'] = {'pipeline': 'monthly-v2', 'rubric': version, 'model': config['llm']['model'],
                                    **screen, 'blockchain_evidence': screen.get('evidence_T', ''),
                                    'economics_evidence': screen.get('evidence_E', '')}
        raw = {k: v for k, v in edition.items() if k not in {'abstract', 'ee'}}
        digest = hashlib.sha256((edition['source'] + ':' + edition['source_id']).encode()).hexdigest()[:24]
        record = {'work_id': 'discovered-' + digest, 'topic_ids': topics, 'verification': verified, 'raw_input': raw}
        outcome['accepted'].append({**row, 'work_id': record['work_id'], 'topics': topics, 'record': record})
        existing |= identities

    selected = [item for item in outcome['accepted'] if in_batch(item, batch or {})] if apply else []
    if selected:
        staged = deepcopy(ledger)
        staged['records'].extend(item['record'] for item in selected)
        built = project(seeds, evidence, staged)          # raises on any inconsistency; nothing written then
        write_json(LEDGER, staged)
        write_json(OUTPUT, built)
        for item in selected:
            store.set_status(item['key'], 'promoted', item['work_id'], directory_id=item['work_id'])
        log(f"promote: applied {len(selected)} of {len(outcome['accepted'])} accepted works -> {len(built['papers'])} in directory")
    written = {item['key'] for item in selected}
    for item in outcome['accepted']:
        if item['key'] not in written:
            store.set_status(item['key'], 'screen_include', 'verified; awaiting --apply')
    log('promote: ' + ', '.join(f'{k}={len(v)}' for k, v in outcome.items()) + ('' if apply else ' (dry run)'))
    return outcome


def _safe_verify(client, record, editions=()):
    try:
        return verify(client, record, editions)
    except (MetadataError, ValueError, KeyError, TypeError) as error:
        return RuntimeError(f'{type(error).__name__}: {error}')


def upgrade_formal(store, config, *, apply=False, keys=None, log=print, client=None):
    """Directory works listed as a preprint whose store work has since gained a formal edition (e.g. from the Scopus
    backfill): verify the formal edition, append it to the ledger with the preprint's topics and scope review, and fold
    the preprint into it through data/work_merges_v1.json. promote() cannot do this because the two share a title."""
    from update import candidate_identity
    seeds, evidence = read_json(SEEDS), read_json(EVIDENCE)
    ledger = read_json(LEDGER)
    directory = project(seeds, evidence, ledger)
    papers = {paper['id']: paper for paper in directory['papers']}
    by_work = {record['work_id']: record for record in ledger['records']}
    merges_path = ROOT / 'data/work_merges_v1.json'
    merges = read_json(merges_path)
    folded = {row['drop'] for row in merges['merges']}
    client = client or LocalDblpClient(ROOT / '.cache/metadata')

    def preprint(paper):
        return venue_policy.is_preprint(paper) or (venue_policy.venue_row(paper.get('venue')) or {}).get('group', '').startswith('Preprint')

    todo = []
    for work in store.works(['in_directory', 'promoted']):
        if keys is not None and work['key'] not in keys:
            continue
        paper = papers.get(work.get('directory_id') or '')
        if not paper or paper['id'] in folded or not preprint(paper) or paper['id'] not in by_work:
            continue
        editions = store.editions(work['key'])
        formal = [e for e in editions if e.get('title') and e.get('year') and not venue_policy.is_preprint(e)
                  and venue_policy.classify(e)['decision'] == 'allow']
        if formal:
            todo.append((work, paper, best_edition(formal), editions))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda item: _safe_verify(client, item[2], item[3]), todo))

    others = {}
    for other in directory['papers']:
        for identity in work_identity(other):
            others.setdefault(identity, set()).add(other['id'])
    accepted, failed = [], []
    for (work, paper, edition, _), verified in zip(todo, results):
        row = {'key': work['key'], 'title': work['title'], 'preprint': paper['id'], 'venue': edition.get('venue')}
        metadata = {} if isinstance(verified, Exception) else (verified.get('metadata') or {})
        if isinstance(verified, Exception) or verified.get('status') != 'verified' or verified.get('conflicts') \
                or venue_policy.is_preprint(metadata) or venue_policy.classify(metadata)['decision'] != 'allow':
            failed.append({**row, 'why': str(verified) if isinstance(verified, Exception) else f"{verified.get('status')} {verified.get('conflicts') or ''}"})
            continue
        clash = {pid for identity in candidate_identity(metadata) for pid in others.get(identity, ())} - {paper['id']}
        shared = {identity for identity in candidate_identity(metadata) if identity[0] != 'title'} & work_identity(paper)
        if shared:                              # the preprint entry already carries this DOI as a linked version
            failed.append({**row, 'why': f'formal edition already linked on the preprint entry {sorted(shared)[:1]}'})
            continue
        if clash:
            failed.append({**row, 'why': f'formal edition already listed as {sorted(clash)}'})
            continue
        verified = deepcopy(verified)
        # Linked versions already listed in the directory (above all the preprint itself) stay their own entries;
        # the build-time merge attaches them, and validate_directory forbids two entries sharing an identifier.
        verified['versions'] = [version for version in verified.get('versions') or []
                                if not {i for i in candidate_identity(version) if i[0] != 'title'} & set(others)]
        verified['scope_review'] = {**by_work[paper['id']]['verification'].get('scope_review', {}), 'upgraded_from': paper['id']}
        raw = {k: v for k, v in edition.items() if k not in {'abstract', 'ee'}}
        digest = hashlib.sha256((edition['source'] + ':' + edition['source_id']).encode()).hexdigest()[:24]
        record = {'work_id': 'discovered-' + digest, 'topic_ids': list(by_work[paper['id']]['topic_ids']), 'verification': verified, 'raw_input': raw}
        if record['work_id'] in by_work:
            continue
        accepted.append({**row, 'record': record, 'formal_venue': metadata.get('venue'), 'year': metadata.get('year')})
    if apply and accepted:
        staged = deepcopy(ledger)
        staged['records'].extend(item['record'] for item in accepted)
        built = project(seeds, evidence, staged)
        write_json(LEDGER, staged)
        write_json(OUTPUT, built)
        for item in accepted:
            merges['merges'].append({'drop': item['preprint'], 'keep': item['record']['work_id'],
                                     'note': f"preprint folded into its {item['year']} {str(item['formal_venue'])[:40]} version: {item['title'][:60]} (formal-version upgrade)"})
        merges_path.write_text(json.dumps(merges, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')   # the file's own layout
    log(f"upgrade: {len(todo)} preprint works with a formal edition; {len(accepted)} verified" + (' and applied' if apply else ' (dry run)') + f"; {len(failed)} not verified")
    return {'accepted': accepted, 'failed': failed}
