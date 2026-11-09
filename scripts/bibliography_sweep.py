"""Retrieve unfiltered bibliographies of ALL linked directory authors, with durable group cursors.

OR groups deduplicate coauthored works within each request. Terminal group cursors
establish OpenAlex retrieval coverage, never scope review or identity correctness.
"""
import argparse
import hashlib
from pathlib import Path
from author_discovery import rank_authors, author_progress
from directory import read_json, write_json
from harvest import CandidateGraph, collect
from metadata import MetadataClient, OPENALEX_FIELDS
from update import exclusive_run

ROOT = Path(__file__).resolve().parents[1]


def roster(directory):
    authors, _ = rank_authors(directory)
    unlinked = [{**r, 'entry_kind': 'unlinked_researcher'} for r in directory['researchers']
                if not r.get('identity_ids', {}).get('openalex')]
    # Fully ID-less bylines do not necessarily have a researcher-table row.
    # Keep each publication observation; a shared name is not identity evidence.
    researcher_ids = {r['id'] for r in directory['researchers']}
    for paper in directory['papers']:
        for edition in [paper, *paper.get('publications', [])]:
            credits = edition.get('author_credits') or [
                {'name': name, 'researcher_id': None} for name in edition.get('authors', [])]
            for index, credit in enumerate(credits):
                if credit.get('researcher_id') in researcher_ids:
                    continue
                basis = f"{paper['id']}|{edition.get('id', paper['id'])}|{index}"
                unlinked.append({'id': 'unlinked-byline-' + hashlib.sha256(basis.encode()).hexdigest()[:20],
                                 'name': credit['name'], 'identity_ids': {},
                                 'entry_kind': 'unlinked_byline', 'work_id': paper['id'],
                                 'edition_id': edition.get('id', paper['id']),
                                 'doi': edition.get('doi'), 'author_position': index,
                                 'status': 'primary_identity_and_bibliography_resolution_pending'})
    return authors, unlinked


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--max-pages', type=int, default=200)
    p.add_argument('--output-dir', type=Path, default=ROOT/'.out/bibliography-sweep')
    p.add_argument('--offline', action='store_true')
    p.add_argument('--page-size',type=int,choices=[50,100,200],default=100)
    p.add_argument('--lock-held',action='store_true',help='Supervisor already owns the scheduled-curation run lock')
    p.add_argument('--plan-only',action='store_true',help='Refresh the full author census and groups without provider requests')
    args = p.parse_args()
    if not 1 <= args.max_pages <= 3000: p.error('max-pages must be 1..3000')
    lock=ROOT/'.out/scheduled-curation/run.lock'
    lock.parent.mkdir(parents=True,exist_ok=True)
    if args.lock_held:
        if not lock.is_dir():p.error('Expected an existing supervisor lock')
    else:
        try:lock.mkdir()
        except FileExistsError:p.error('Another curation run owns the shared lock')
    try:
        with exclusive_run(args.output_dir):return run(args)
    finally:
        if not args.lock_held:lock.rmdir()


def run(args):
    out = args.output_dir; out.mkdir(parents=True, exist_ok=True)
    directory = read_json(ROOT/'site/data/directory.json')
    authors, unlinked = roster(directory)
    frontier = ROOT/'.cache/author-discovery/frontier.json'
    progress = author_progress(read_json(ROOT/'.out/scheduled-curation/state.json'), read_json(frontier))
    path = out/'manifest.json'
    manifest = read_json(path) if path.exists() else {'schema_version':1, 'groups':[], 'graph_paths':[]}
    grouped = {i for g in manifest['groups'] for i in g['author_ids']}
    pending = [a['id'] for a in authors if a['id'] not in grouped and not progress.get(a['id'],{}).get('complete')]
    for start in range(0, len(pending), 25):
        ids = pending[start:start+25]
        manifest['groups'].append({'id':hashlib.sha256('|'.join(ids).encode()).hexdigest()[:16],
                                  'author_ids':ids, 'next_cursor':'*', 'complete':False, 'pages':0})
    manifest.update(authors=authors, unlinked_authors=unlinked,
        limitations='Indexed identity links require scrutiny. Full provider retrieval is not full publication coverage or relevance review. Unlinked entries include researcher rows and publication byline observations, not a count of unique people. ID-less authors require primary bibliography matching; shared names are not merged.',
        filter_policy='No topic, venue, year, citation-count, abstract, or language filter; exclude only retracted records.')
    manifest.update(complete_authors=sum(bool(progress.get(a['id'],{}).get('complete')) for a in authors),linked_authors=len(authors))
    if args.plan_only:
        write_json(path,manifest)
        return 0
    client = MetadataClient(ROOT/'.cache/author-discovery', offline=args.offline)
    used = 0
    for group in manifest['groups']:
        if group['complete']: continue
        while used < args.max_pages:
            graph = CandidateGraph(directory)
            count = min(10, args.max_pages-used)
            collect(client, graph, 'openalex', 'author-group:'+group['id'],
                    {'filter':'authorships.author.id:'+'|'.join(group['author_ids'])+',is_retracted:false',
                     'sort':'publication_date:desc','select':OPENALEX_FIELDS+',abstract_inverted_index'}, count, start_cursor=group['next_cursor'],page_size=args.page_size)
            coverage = graph.coverage[-1]
            observed = group.setdefault('observed_author_ids', [])
            observed[:] = sorted(set(observed) | {a.get('ids',{}).get('openalex')
                for node in graph.nodes.values() for source in node['sources'].values()
                for a in source.get('authors',[]) if a.get('ids',{}).get('openalex') in group['author_ids']})
            graph_path = out/f"group-{group['id']}-page-{group['pages']:05d}.json"
            write_json(graph_path, graph.snapshot())
            if str(graph_path) not in manifest['graph_paths']: manifest['graph_paths'].append(str(graph_path))
            used += max(1,coverage['pages'])
            group.update(next_cursor=coverage['next_cursor'], complete=coverage['complete'],
                         pages=group['pages']+coverage['pages'], last_status=coverage['status'],
                         last_report=str(graph_path))
            if group['complete'] and not args.offline:
                for identifier in group['author_ids']:
                    progress[identifier] = {'complete':True, 'next_cursor':None, 'last_status':'ok',
                        'last_report':str(path), 'basis':'terminal_OR_group_cursor', 'group_id':group['id']}
                write_json(frontier, progress)
            manifest.update(complete_authors=sum(bool(progress.get(a['id'],{}).get('complete')) for a in authors),
                            linked_authors=len(authors), pages_this_run=used)
            write_json(path, manifest)
            print(f"pages={used} group={group['id']} group_complete={group['complete']} complete_authors={manifest['complete_authors']}/{len(authors)}", flush=True)
            if coverage['status'] != 'ok':
                manifest.setdefault('failures',[]).append(coverage)
                write_json(path,manifest)
                return 2  # back off, never mark failure as coverage
            if group['complete']: break
        if used >= args.max_pages: break
    write_json(path, manifest)


if __name__ == '__main__': raise SystemExit(main())
