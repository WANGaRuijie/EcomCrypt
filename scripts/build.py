"""Capture seed evidence and build a deterministic, offline Pages dataset."""

import html
import json
import argparse
from collections import Counter
from copy import deepcopy
import os
from pathlib import Path

from directory import append_work, new_directory, read_json, validate_directory, work_keys, write_json


ROOT = Path(__file__).resolve().parents[1]
SEEDS = ROOT / "data/golden_seeds_v1.json"
EVIDENCE = ROOT / "data/verification_v1.json"
PRIMARY = ROOT / "data/primary_evidence_v1.json"
PUBLICATIONS = ROOT / "data/publication_evidence_v1.json"
LEDGER = ROOT / "data/accepted_updates_v1.json"
OUTPUT = ROOT / "site/data/directory.json"


def verify(seed_data, cache, refresh, offline):
    from metadata import MetadataClient, normalize_title

    client = MetadataClient(
        cache, refresh=refresh, offline=offline, contact=os.getenv("METADATA_CONTACT"),
        openalex_key=os.getenv("OPENALEX_API_KEY"),
    )
    primary = read_json(PRIMARY)["records"]
    records = {}
    for seed in seed_data["papers"]:
        official = deepcopy(primary.get(seed["id"]))
        alternate_title = official["metadata"]["title"] if official else seed["title"]
        indexed = client.verify({**seed, "title": alternate_title})
        if official is None:
            records[seed["id"]] = indexed
            continue
        canonical = official["metadata"]
        indexed_metadata = indexed.get("metadata") or {}
        if canonical["doi"] and canonical["doi"] == indexed_metadata.get("doi"):
            indexed_authors = indexed_metadata.get("authors") or []
            if [normalize_title(a["name"]) for a in indexed_authors] == [
                normalize_title(a["name"]) for a in canonical["authors"]
            ]:
                canonical["authors"] = [
                    {**enriched, "name": original["name"]}
                    for original, enriched in zip(canonical["authors"], indexed_authors)
                ]
            canonical["source_ids"].update(indexed_metadata.get("source_ids") or {})
            official["versions"] = indexed.get("versions") or []
        official["index_result"] = indexed
        records[seed["id"]] = official
    return {
        "schema_version": 1,
        "collection": seed_data["collection"],
        "records": records,
    }


def merge_duplicates(directory):
    """Fold works confirmed to be one paper (data/work_merges_v1.json) into one entry; the ledger keeps both."""
    path = ROOT / 'data/work_merges_v1.json'
    if not path.exists():
        return
    from venue_policy import is_preprint, venue_row
    papers = {paper['id']: paper for paper in directory['papers']}
    for row in read_json(path)['merges']:
        drop, keep = papers.get(row['drop']), papers.get(row['keep'])
        if drop is None or keep is None:
            continue
        directory['papers'].remove(drop)
        edition = {key: value for key, value in drop.items() if key not in {'versions', 'publications'}}
        unrefereed = is_preprint(drop) or (venue_row(drop.get('venue')) or {}).get('group', '').startswith('Preprint')
        keep.setdefault('versions' if unrefereed else 'publications', []).append(edition)
        if drop.get('versions'):
            keep.setdefault('versions', []).extend(drop['versions'])
        if drop.get('publications'):
            keep.setdefault('publications', []).extend(drop['publications'])


def project(seed_data, evidence, ledger=None):
    from metadata import _resolve_edition, normalize_title

    if evidence["schema_version"] != 1 or evidence["collection"] != seed_data["collection"]:
        raise ValueError("evidence does not belong to the selected collection")
    seeds = seed_data["papers"]
    if len(seeds) != 50 or len(seed_data["topics"]) != 9:
        raise ValueError("Golden Seeds v1 must have 50 inputs and nine topics")
    expected = {f"gs-{number:03}" for number in range(1, 51)}
    if {seed["id"] for seed in seeds} != expected or set(evidence["records"]) != expected:
        raise ValueError("missing or unexpected seed IDs")

    directory = new_directory(seed_data["topics"])
    directory['topics'].extend([{'id':'governance','name':'Blockchain Governance'},
        {'id':'tokenomics','name':'Tokenomics & Adoption'}, {'id':'economic-security','name':'Economic Security'},
        {'id':'incentive-systems','name':'Incentive-Aware Systems Design'}])
    for topic in directory['topics']:
        if topic['id'] == 'rational-cryptography':
            topic['name'] = 'Rational Cryptography and Security'
        if topic['id'] == 'economics':topic['name']='Markets & Platforms'
    publication_evidence = read_json(PUBLICATIONS)
    seen_work = {}
    for seed in seeds:
        result = deepcopy(evidence["records"][seed["id"]])
        metadata = result.get("metadata") or {}
        versions = result.setdefault("versions", [])
        for supplement in publication_evidence["linked_publications"].get(seed["id"], []):
            if metadata.get("doi") == supplement["doi"] or any(v.get("doi") == supplement["doi"] for v in versions):
                continue
            identities = {
                normalize_title(author["name"]): author.get("ids", {})
                for author in metadata.get("authors", [])
            }
            versions.append({
                **supplement, "authors": [
                    {"name": name, "ids": identities.get(normalize_title(name), {})}
                    for name in supplement["authors"]
                ],
            })
        for doi in publication_evidence["linked_dois"].get(seed["id"], []):
            if metadata.get("doi") == doi or any(version.get("doi") == doi for version in versions):
                continue
            matched = [
                row for row in (result.get("index_result") or result)["evidence"]
                if row.get("doi") == doi and row.get("match") in {"exact_title", "seed_venue_year_title_variant"}
            ]
            if not matched:
                raise ValueError(f"missing edition evidence for {seed['id']} DOI {doi}")
            edition, conflicts = _resolve_edition(matched, {})
            if conflicts:
                raise ValueError(f"conflicting edition evidence for {seed['id']} DOI {doi}")
            versions.append(edition)
        for edition in [metadata, *versions]:
            source = publication_evidence["venues"].get(edition.get("doi"))
            if source:
                edition.update(venue=source["name"], kind="conference-paper", venue_source=source["source"])
        keys = work_keys({**metadata, "versions": result.get("versions") or metadata.get("versions") or []})
        previous = {seen_work[key] for key in keys if key in seen_work}
        if previous:
            raise ValueError(f"overlapping seeds {seed['id']} and {sorted(previous)} require evidence review")
        seen_work.update(dict.fromkeys(keys, seed["id"]))
        append_work(
            directory, work_id=seed["id"], topic_ids=seed["topic_ids"],
            verification=result, raw_input=seed,
        )
    if ledger is not None:
        if ledger.get("schema_version") != 1 or not isinstance(ledger.get("records"), list):
            raise ValueError("unsupported accepted-update ledger")
        from venue_policy import work_denial
        scope_path = ROOT / "data/scope_removals_v2.json"
        scope_removed = {row["work_id"] for row in read_json(scope_path)["records"]} if scope_path.exists() else set()
        for record in ledger["records"]:
            if record["work_id"].startswith("gs-") or record["verification"]["status"] != "verified":
                raise ValueError("accepted updates require a separate ID and verified metadata")
            # Venue-level exclusions (data/venue_policy_v2.json) are applied at build
            # time so the append-only ledger keeps the record and removal is reversible.
            if record["work_id"] in scope_removed or work_denial(
                    record["verification"]["metadata"], record["verification"].get("versions", [])):
                continue
            record = deepcopy(record)
            result = record["verification"]
            for edition in [result["metadata"], *result.get("versions", [])]:
                edition.update({key: html.unescape(edition[key]) for key in ("title", "venue") if edition.get(key)})
                source = publication_evidence["venues"].get(edition.get("doi"))
                if source:
                    edition.update(venue=source["name"], kind="conference-paper", venue_source=source["source"])
            append_work(directory, **record)
    context = ROOT / 'data/foundational_context_v1.json'
    if context.exists():
        for row in read_json(context)['records']:
            metadata=row['verification']['metadata']
            keys=work_keys({**metadata,'versions':row['verification'].get('versions',[])})
            matches=[p for p in directory['papers'] if keys & work_keys(p)]
            paper=matches[0] if matches else append_work(directory,**{k:row[k] for k in ('work_id','topic_ids','verification','raw_input')})
            paper.update(collection_basis='foundational_context',inclusion_note=row['inclusion_note'])
    supplemental = ROOT / 'data/additional_seeds_v1.json'
    if supplemental.exists():
        from update import work_identity
        for row in read_json(supplemental)['records']:
            row = deepcopy(row)
            for edition in [row.get('verification', {}).get('metadata') or {}, *row.get('verification', {}).get('versions', [])]:
                source = publication_evidence['venues'].get(edition.get('doi'))
                if source:
                    edition.update(venue=source['name'],kind='conference-paper',venue_source=source['source'])
            metadata = row.get('verification', {}).get('metadata') or {}
            keys = work_identity({**metadata, 'raw_input': row['raw_input'],
                                  'versions': row.get('verification', {}).get('versions', [])})
            matches = [paper for paper in directory['papers'] if keys & work_identity(paper)]
            if matches:
                for paper in matches:
                    paper.setdefault('supplemental_seed_inputs', []).append(row['raw_input'])
            else:
                append_work(directory, **{key:row[key] for key in ('work_id','topic_ids','verification','raw_input')})
    watch = ROOT / 'data/publication_watch_v1.json'
    if watch.exists():
        from publications import apply_watch
        apply_watch(directory, read_json(watch))
    validate_directory(directory)
    from topics import annotate
    reviews = {row['work_id']:row['verification'].get('scope_review', {}) for row in (ledger or {}).get('records', [])}
    for paper in directory['papers']:
        review=reviews.get(paper['id'], {})
        annotate(paper, ' '.join(review.get(key, '') for key in ('blockchain_evidence','economics_evidence')))
    topic_reviews=ROOT/'data/topic_reviews_v1.json'
    if topic_reviews.exists():
        by_id={p['id']:p for p in directory['papers']}
        for row in read_json(topic_reviews)['records']:
            paper=by_id.get(row['work_id'])
            # Partial projections can intentionally omit ledger works.
            if paper is None:continue
            for topic in row['add_topic_ids']:
                if topic not in {t['id'] for t in directory['topics']}:raise ValueError('Unknown reviewed topic')
                if topic not in paper['topic_ids']:paper['topic_ids'].append(topic)
            paper.setdefault('topic_annotations',[]).append({'method':'editorial_topic_review_v1',**row})
    directory['papers'].sort(key=lambda paper: 0 if paper['id'].startswith('gs-') else 1 if paper['id'].startswith('extra-') else 2 if paper.get('collection_basis')=='foundational_context' else 3)
    aliases = ROOT / 'data/author_display_aliases_v1.json'
    if aliases.exists():directory['author_display_aliases']=read_json(aliases)['groups']
    acceptances=ROOT/'data/venue_acceptance_evidence_v1.json'
    if acceptances.exists():
        for row in read_json(acceptances)['records']:
            for paper in directory['papers']:
                if normalize_title(paper['title'])==normalize_title(row['title']):
                    paper.update(accepted_venue=row['venue'],acceptance_source=row['source'],publication_status='accepted')
    merge_duplicates(directory)
    from topics import apply_taxonomy
    apply_taxonomy(directory)
    homonyms=ROOT/'data/author_homonyms_v1.json'
    if homonyms.exists():
        for row in read_json(homonyms)['records']:
            for paper in directory['papers']:
                if row['name'] in paper.get('authors',[]) and (paper['id'] in row['work_ids'] or set(row.get('coauthors_any',[]))&set(paper['authors'])):
                    paper['authors']=[row['display'] if a==row['name'] else a for a in paper['authors']]
                    for credit in paper.get('author_credits',[]):
                        if credit['name']==row['name']:credit['name']=row['display']
    from venue_policy import is_top,venue_row
    ABBREVIATIONS=read_json(ROOT/'data/journal_abbreviations_v1.json')['abbreviations']   # journals show their ISO 4 abbreviation
    for edition in (e for paper in directory['papers'] for e in [paper,*paper.get('publications',[])]):
        row=venue_row(edition.get('accepted_venue') or edition.get('venue'))       # the site shows this tag: one matcher for screening and display
        edition['venue_tag']={'label':row['label'],'group':row['group'],**({'top':True} if is_top(row['label']) else {}),**({'display':ABBREVIATIONS[row['id']]} if row['id'] in ABBREVIATIONS else {})} if row else None
    return directory


SITE_CATALOG = ROOT / "site/data/catalog.json"
SITE_DROP = {"legacy_topic_ids", "topic_annotations", "status", "source_ids_detail"}


def site_catalog(directory):
    """What the browser loads: directory.json without the fields the site never reads, written without indentation.
    directory.json stays the full, reviewable projection (tests compare it); the site fetches this file instead."""
    def slim(paper):
        out = {key: value for key, value in paper.items() if key not in SITE_DROP}
        if isinstance(out.get("raw_input"), dict):
            out["raw_input"] = {"title": out["raw_input"].get("title")}   # the site only searches its title
        return out
    return {
        "schema_version": directory["schema_version"],
        "topics": directory["topics"],
        "institutions": [],
        "researchers": [{"id": r["id"], "name": r["name"]} for r in directory["researchers"]],
        "author_display_aliases": directory.get("author_display_aliases", []),
        "papers": [{**slim(paper), **({"publications": [slim(p) for p in paper["publications"]]} if paper.get("publications") else {})}
                   for paper in directory["papers"]],
    }


def write_site_catalog(directory):
    text = json.dumps(site_catalog(directory), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    SITE_CATALOG.write_text(text + "\n", encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("build", "verify", "check"))
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache/metadata")
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument("--refresh", action="store_true", help="refresh cached source responses")
    parser.add_argument("--offline", action="store_true", help="reconcile locally cached source responses")
    args = parser.parse_args()
    seeds = read_json(SEEDS)
    if args.offline and args.refresh:
        parser.error("--offline and --refresh are mutually exclusive")
    evidence = (
        verify(seeds, args.cache, args.refresh, args.offline)
        if args.mode == "verify" else read_json(args.evidence)
    )
    ledger = read_json(args.ledger) if args.ledger.exists() else None
    directory = project(seeds, evidence, ledger)
    if args.mode == "check":
        if read_json(args.output) != directory:
            raise SystemExit("Pages snapshot is stale. Run python scripts/build.py build.")
        if not SITE_CATALOG.exists() or read_json(SITE_CATALOG) != json.loads(json.dumps(site_catalog(directory), ensure_ascii=False)):
            raise SystemExit("site/data/catalog.json is stale. Run python scripts/build.py build.")
    else:
        if args.mode == "verify":
            previous = read_json(args.evidence)["records"] if args.evidence.exists() else {}
            rank = {"unverified": 0, "ambiguous": 0, "partial": 1, "verified": 2}
            lost = [
                seed_id for seed_id, old in previous.items()
                if rank[evidence["records"][seed_id]["status"]] < rank[old["status"]]
            ]
            if lost:
                raise SystemExit(f"Evidence regressed for {', '.join(lost)}. Snapshot kept.")
            write_json(args.evidence, evidence)
        write_json(args.output, directory)
        if args.output == OUTPUT:
            write_site_catalog(directory)
    counts = Counter(paper["status"] for paper in directory["papers"])
    print(f"{len(directory['papers'])} papers, {len(directory['topics'])} topics, "
          f"{len(directory['researchers'])} researchers, {len(directory['institutions'])} institutions")
    print(", ".join(f"{key}={counts[key]}" for key in sorted(counts)))


if __name__ == "__main__":
    main()
