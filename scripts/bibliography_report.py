"""Reconcile retrieved author bibliographies and nominate review candidates, without adoption."""
import argparse
from collections import Counter
from pathlib import Path
from directory import read_json,write_json
from update import work_identity
from evidence_review import intersection_title
from metadata import normalize_title
from expand import editorial_scope_review

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,default=ROOT/'.out/bibliography-sweep')
    args=p.parse_args();out=args.output_dir
    manifest=read_json(out/'manifest.json')
    directory=read_json(ROOT/'site/data/directory.json')
    known=set().union(*(work_identity(p) for p in directory['papers']))
    raw={};observed=Counter();graphs=[]
    for path in manifest['graph_paths']:
        graph=read_json(path);graphs.append(str(Path(path).relative_to(ROOT)))
        for node in graph['nodes']:
            for record in node['sources']:
                if record['source_id'] in raw:continue
                raw[record['source_id']]=record
                for author in record.get('authors',[]):
                    identifier=author.get('ids',{}).get('openalex')
                    if identifier:observed[identifier]+=1
    candidates=[]
    history=[]
    for path in (ROOT/'data').glob('discovery_campaign_v*.json'):history.extend(read_json(path)['records'])
    for path in (ROOT/'.out/scheduled-curation').glob('round-*/screen.json'):history.extend(read_json(path)['rows'])
    processed={row.get('classification',{}).get('id') for row in history}
    old_keys=set().union(*(work_identity(row) for row in history))
    for record in raw.values():
        if not intersection_title(record['title']) or work_identity(record)&known:continue
        candidates.append({'raw_input':record,'status':'requires_scope_contribution_metadata_review',
                           'previously_screened_identity':record['source_id'] in processed or bool(work_identity(record)&old_keys),
                           'editorial_hold':editorial_scope_review(record)})
    write_json(out/'review-candidates.json',{'schema_version':1,'records':candidates,
        'policy':'Title signals nominate review only. Versions may remain duplicated until verified. No author fame/venue/count-based adoption.'})
    write_json(out/'coverage.json',{'linked_authors':manifest['linked_authors'],
        'terminal_provider_bibliographies':manifest['complete_authors'],
        'pending_groups':[g for g in manifest['groups'] if not g['complete']],
        'unlinked_author_records':manifest['unlinked_authors'],
        'distinct_source_records':len(raw),'title_signal_candidates':len(candidates),
        'candidate_title_groups':len({normalize_title(r['raw_input']['title']) for r in candidates}),
        'new_unseen_title_signal_source_records':sum(not r['previously_screened_identity'] for r in candidates),
        'new_unseen_title_signal_groups':len({normalize_title(r['raw_input']['title']) for r in candidates if not r['previously_screened_identity']}),
        'author_observed_counts':{a['id']:observed[a['id']] for a in manifest['authors']},
        'limitations':manifest['limitations'],'graph_paths':graphs,
        'adopted':0,'paid_llm_calls':0})
    print(f"Retrieved {len(raw)} distinct source records; {len(candidates)} title-signal nominations, not adoptions.")


if __name__=='__main__':main()
