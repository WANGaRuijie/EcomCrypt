"""Collect a bibliographic candidate graph without publishing to the directory."""

import argparse
from collections import Counter
from datetime import date
from pathlib import Path
import re

from directory import read_json, write_json
from metadata import MetadataClient, MetadataError, OPENALEX_FIELDS, _records
from update import seed_from_record, title_topics
from venue_sources import resolve_sources


ROOT = Path(__file__).resolve().parents[1]
PAGE_SIZE = 50
PREPRINT_QUERY = (
    'blockchain OR bitcoin OR ethereum OR "automated market maker" OR '
    '"maximal extractable value" OR "transaction fee mechanism"'
)


def seed_anchors(work):
    """Use verified identifiers from the work and its linked publication versions."""
    rows = [work, *work.get("publications", []), *work.get("versions", [])]
    return sorted({identifier for row in rows
                   if isinstance(identifier := (row.get("source_ids") or {}).get("openalex"), str)
                   and re.fullmatch(r"W\d+", identifier)})


def collect_citations(client, graph, work_id, anchor, window, pages, state=None):
    lane = f'citations:{work_id}:{anchor}'
    state = state or {}
    saved = state.get('discovery_lane_progress', {}).get(lane, {})
    compatible = saved.get('window') == window
    if compatible and saved.get('complete'):
        graph.coverage.append({'lane': lane, 'status': 'already_complete', 'records': 0,
                               'pages': 0, 'complete': True, 'next_cursor': None,
                               'window': window, 'reused_terminal_cursor': True})
        return
    cursor = saved.get('next_cursor') if compatible else None
    # Legacy cursors belong to this project's unchanged citation date window.
    if not saved:
        cursor = state.get('discovery_lane_cursors', {}).get(lane)
    collect(client, graph, 'openalex', lane, {'filter': f'{window},cites:{anchor}'},
            pages, cites=work_id, start_cursor=cursor or '*')
    graph.coverage[-1]['window'] = window


class CandidateGraph:
    def __init__(self, directory):
        self.nodes = {}
        self.edges = set()
        self.coverage = []
        self.anchors = {
            work["id"]: {"title": work["title"], "topic_ids": work["topic_ids"]}
            for work in directory["papers"]
        }
        self.indexed = {
            ("doi", row["doi"])
            for work in directory["papers"]
            for row in [work, *work.get("versions", [])]
            if row.get("doi")
        }
        self.indexed.update(
            (source, identifier)
            for work in directory["papers"]
            for row in [work, *work.get("versions", [])]
            for source, identifier in (row.get("source_ids") or {}).items()
        )

    def add(self, record, lane):
        provider_key = (record["source"], record["source_id"])
        doi = record.get("doi")
        key = f"doi:{doi}" if doi else ":".join(provider_key)
        node = self.nodes.setdefault(key, {
            "id": key, "title": record["title"], "topic_hints": title_topics(record["title"]),
            "known": False, "sources": {}, "lanes": set(),
        })
        node["known"] |= provider_key in self.indexed or ("doi", doi) in self.indexed
        node["sources"][":".join(provider_key)] = record
        node["lanes"].add(lane)
        return key

    def snapshot(self):
        snapshot = {
            "schema_version": 1,
            "coverage": self.coverage,
            "anchors": self.anchors,
            "nodes": [
                {**node, "sources": list(node["sources"].values()), "lanes": sorted(node["lanes"])}
                for node in self.nodes.values()
            ],
            "edges": [
                {"from": start, "to": end, "relation": "cites", "source": "openalex"}
                for start, end in sorted(self.edges)
            ],
        }
        snapshot["review_queue"] = rank_candidates(snapshot)
        return snapshot


def rank_candidates(snapshot):
    seed_neighbors = {}
    for edge in snapshot["edges"]:
        start, end = edge["from"], edge["to"]
        for node, seed in ((start, end), (end, start)):
            if seed.startswith("gs-"):
                seed_neighbors.setdefault(node, set()).add(seed)
    queue = []
    for node in snapshot["nodes"]:
        seeds = sorted(seed_neighbors.get(node["id"], ()))
        hints = node["topic_hints"]
        if not node["known"] and (hints or len(seeds) > 1):
            queue.append({"id": node["id"], "topic_hints": hints, "connected_seeds": seeds})
    return sorted(queue, key=lambda row: (
        not bool(row["topic_hints"]), -len(row["connected_seeds"]), row["id"],
    ))


def verify_queue(client, snapshot, limit):
    nodes = {node["id"]: node for node in snapshot["nodes"]}
    for item in snapshot["review_queue"][:limit]:
        observed = nodes[item["id"]]["sources"]
        item["verification"] = client.verify(seed_from_record(observed[0]), observed=observed)


def collect(client, graph, source, lane, params, pages, *, cites=None, cited_by=None, start_cursor="*", page_size=PAGE_SIZE):
    if not 1 <= page_size <= 200: raise ValueError('Invalid provider page size')
    coverage = {"lane": lane, "status": "ok", "pages": 0, "records": 0, "complete": False, "queries": []}
    graph.coverage.append(coverage)
    cursor = start_cursor
    if source == "openalex":
        coverage.update(start_cursor=cursor, next_cursor=cursor)
    for page in range(pages):
        request = (
            {"select": OPENALEX_FIELDS, "per_page": page_size, **params, "cursor": cursor}
            if source == "openalex"
            else {"format": "json", "h": PAGE_SIZE, "f": page * PAGE_SIZE, **params}
        )
        try:
            envelope = client._fetch(source, request)
            payload = envelope["payload"]
            records = _records(source, payload)
        except MetadataError as exc:
            coverage.update(status="unavailable", reason=str(exc))
            return
        coverage["queries"].append(envelope["url"])
        for record in records:
            key = graph.add({
                **record, "query_url": envelope["url"], "retrieved_at": envelope["retrieved_at"],
            }, lane)
            if cites:
                graph.edges.add((key, cites))
            if cited_by:
                graph.edges.add((cited_by, key))
        coverage["pages"] += 1
        coverage["records"] += len(records)
        if source == "openalex":
            cursor = payload.get("meta", {}).get("next_cursor")
            coverage["complete"] = not cursor or not records
            coverage["next_cursor"] = cursor
        else:
            hits = payload["result"]["hits"]
            coverage["complete"] = not records or (page + 1) * PAGE_SIZE >= int(hits["@total"])
            coverage["next_offset"] = None if coverage["complete"] else (page + 1) * PAGE_SIZE
        if coverage["complete"]:
            return


def references(client, graph, work_id, anchor, window):
    lane = f"references:{work_id}"
    try:
        envelope = client._fetch("openalex", {
            "filter": f"openalex:{anchor}", "select": "id,referenced_works", "per_page": 1,
        })
        work = next(iter(envelope["payload"]["results"]), {})
    except MetadataError as exc:
        graph.coverage.append({"lane": lane, "status": "unavailable", "reason": str(exc)})
        return
    identifiers = [
        value.rsplit("/", 1)[-1] for value in work.get("referenced_works", [])
        if re.fullmatch(r"(?:https://openalex.org/)?W\d+", value)
    ]
    if not identifiers:
        graph.coverage.append({"lane": lane, "status": "ok", "records": 0, "complete": True})
    for offset in range(0, len(identifiers), PAGE_SIZE):
        batch = "|".join(identifiers[offset:offset + PAGE_SIZE])
        collect(client, graph, "openalex", f"{lane}:{offset}", {"filter": f"{window},openalex:{batch}"},
                1, cited_by=work_id)


def hydrate_dblp(client, graph):
    """Join proceedings records to OpenAlex by exact DOI for abstract screening."""
    dois = sorted({record["doi"] for node in graph.nodes.values()
                   for record in node["sources"].values()
                   if record["source"] == "dblp" and record.get("doi")})
    for offset in range(0, len(dois), PAGE_SIZE):
        collect(client, graph, "openalex", f"dblp-doi-bridge:{offset}",
                {"filter": "doi:" + "|".join(dois[offset:offset + PAGE_SIZE])}, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-year", type=int, required=True)
    parser.add_argument("--to-year", type=int, default=date.today().year)
    parser.add_argument("--pages", type=int, choices=range(1, 21), default=1)
    parser.add_argument("--seed-offset", type=int, default=0)
    parser.add_argument("--seed-limit", type=int, choices=range(3001), default=4)
    parser.add_argument("--proceedings", action="append", default=[], metavar="DBLP_TOC")
    parser.add_argument("--hydrate-dblp", action="store_true", help="Join DBLP DOI records to OpenAlex for abstract screening")
    parser.add_argument("--source", action="append", default=[], metavar="OPENALEX_SOURCE_ID")
    parser.add_argument("--venue", action="append", default=[], metavar="REGISTRY_ID")
    parser.add_argument("--preprints", action="store_true")
    parser.add_argument("--year-slices", action="store_true", help="Query each venue and preprint index separately by year")
    parser.add_argument("--verify-top", type=int, choices=range(21), default=0, metavar="0..20")
    parser.add_argument("--include-reviewed", action="store_true", help="Also traverse verified works already adopted from earlier passes")
    parser.add_argument("--offline", action="store_true", help="Replay locally cached index pages")
    parser.add_argument('--resume-citations', action='store_true', help='Continue saved project citation cursors instead of restarting pages')
    parser.add_argument("--seed-id", action="append", default=[], help="Discover from exact reviewed work IDs instead of rank offsets")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1900 <= args.from_year <= args.to_year <= date.today().year + 1 or args.seed_offset < 0:
        parser.error("invalid year range or seed offset")
    if any(not re.fullmatch(r"db/conf/[\w/-]+\.bht", toc) for toc in args.proceedings):
        parser.error("use a DBLP BHT key such as db/conf/atal/aamas2024.bht")
    if any(not re.fullmatch(r"S\d+", source) for source in args.source):
        parser.error("OpenAlex source IDs must look like S123")
    registry = {row["id"]: row for row in read_json(ROOT / "data/venue_registry_v1.json")["venues"]}
    if any(identifier not in registry for identifier in args.venue):
        parser.error("unknown venue ID, see VENUES.md")

    directory = read_json(ROOT / "site/data/directory.json")
    graph = CandidateGraph(directory)
    client = MetadataClient(ROOT / ".cache/harvest", offline=args.offline)
    resolved = {}
    for identifier in dict.fromkeys(args.venue):
        venue = registry[identifier]
        if venue["kind"] not in {"conference", "journal"}:
            graph.coverage.append({
                "lane": f"venue-resolution:{identifier}", "status": "unresolved",
                "reason": "requires_edition_or_program_source", "complete": False,
            })
            continue
        try:
            resolution = resolve_sources(client, venue)
        except MetadataError as exc:
            graph.coverage.append({"lane": f"venue-resolution:{identifier}", "status": "unavailable", "reason": str(exc)})
            continue
        graph.coverage.append(resolution)
        if resolution["status"] == "ok":
            source_id = resolution["matches"][0]["id"].rsplit("/", 1)[-1]
            resolved[identifier] = source_id
    def date_window(start, end):
        return f"from_publication_date:{start}-01-01,to_publication_date:{end}-12-31,is_retracted:false"

    window = date_window(args.from_year, args.to_year)
    seeds = [
        work for work in directory["papers"]
        if work["id"].startswith(("gs-", "extra-", "foundation-")) or (args.include_reviewed and work["status"] == "verified")
    ]
    if args.seed_id:
        by_id={work['id']:work for work in directory['papers']}
        if set(args.seed_id)-set(by_id):parser.error('unknown seed work ID')
        selected_seeds=[by_id[i] for i in dict.fromkeys(args.seed_id)]
    else:selected_seeds=seeds[args.seed_offset:args.seed_offset + args.seed_limit]
    statepath = ROOT/'.out/scheduled-curation/state.json'
    citation_state = read_json(statepath) if args.resume_citations and statepath.exists() else {}
    for work in selected_seeds:
        anchors = seed_anchors(work)
        if not anchors:
            graph.coverage.append({"lane": f"seed:{work['id']}", "status": "unavailable", "reason": "no_openalex_id"})
        for anchor in anchors:
            collect_citations(client, graph, work['id'], anchor, window, args.pages, citation_state)
            references(client, graph, work["id"], anchor, window)
    for toc in args.proceedings:
        collect(client, graph, "dblp", f"proceedings:{toc}", {"q": f"toc:{toc}:"}, args.pages)
    if args.hydrate_dblp:
        hydrate_dblp(client, graph)
    slices = [("", window)]
    if args.year_slices:
        slices = [(f":{year}", date_window(year, year)) for year in range(args.from_year, args.to_year + 1)]
    for suffix, dates in slices:
        for identifier, source_id in resolved.items():
            collect(client, graph, "openalex", f"source:{source_id}:venue={identifier}{suffix}",
                    {"filter": f"{dates},locations.source.id:{source_id}"}, args.pages)
        for source in args.source:
            collect(client, graph, "openalex", f"source:{source}{suffix}",
                    {"filter": f"{dates},primary_location.source.id:{source}"}, args.pages)
        if args.preprints:
            collect(client, graph, "openalex", f"preprints{suffix}", {
                "filter": f"{dates},type:preprint", "search": PREPRINT_QUERY,
            }, args.pages)
    snapshot = graph.snapshot()
    verify_queue(client, snapshot, args.verify_top)
    write_json(args.output, snapshot)
    counts = Counter(row["status"] for row in snapshot["coverage"])
    print(f"{len(snapshot['nodes'])} candidates, {len(snapshot['edges'])} citation edges, lanes {dict(counts)}")
    return 0 if counts["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
