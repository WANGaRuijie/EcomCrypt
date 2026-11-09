"""Deepen bibliographies of identified relevant authors; citation edges nominate new authors."""
import argparse,re
from collections import Counter
from pathlib import Path
from directory import read_json,write_json
from harvest import CandidateGraph,collect
from metadata import MetadataClient
from quality import assess

ROOT=Path(__file__).resolve().parents[1]

def author_progress(state, saved):
    """Migrate only already visited lanes; keep unfinished cursors distinct from completion."""
    progress=dict(saved)
    for identifier in state.get('processed_author_ids',[]):
        cursor=state.get('discovery_lane_cursors',{}).get('author:'+identifier)
        progress.setdefault(identifier,{'complete':not bool(cursor),'next_cursor':cursor,'basis':'prior_successful_coverage'})
    return progress

def select_authors(ranked, priority_ids, progress, limit, offset=0, requested_ids=()):
    by_id={a['id']:a for a in ranked}
    if requested_ids:return [by_id[i] for i in dict.fromkeys(requested_ids)][:limit]
    ordered=[by_id[i] for i in priority_ids if i in by_id]
    ordered += [a for a in ranked if progress.get(a['id'],{}).get('next_cursor')]
    ordered += ranked[offset:]
    result=[];seen=set()
    for row in ordered:
        if row['id'] in seen or progress.get(row['id'],{}).get('complete'):continue
        seen.add(row['id']);result.append(row)
        if len(result)==limit:break
    return result
def rank_authors(directory, graphs=()):
    scores=Counter();evidence={}
    for paper in directory['papers']:
        # Every adopted work has passed editorial review. Venue priority affects
        # ordering, never eligibility to inspect an existing author's bibliography.
        identifiers={identifier for edition in [paper,*paper.get('publications',[])]
                     for identifier in edition.get('researcher_ids',[])}
        for identifier in identifiers:
            scores[identifier]+=3 if paper['id'].startswith(('gs-','extra-','foundation-')) else (2 if assess(paper)['decision']=='priority' else 1)
            evidence.setdefault(identifier,[]).append(paper['id'])
    rows={}
    for researcher in directory['researchers']:
        if scores[researcher['id']]<=0:continue
        identifier=researcher['identity_ids'].get('openalex')
        if identifier and re.fullmatch(r'A\d+',identifier):
            row=rows.setdefault(identifier,{'id':identifier,'name':researcher['name'],'score':0,
                         'evidence':[],'status':'indexed_relevant_author'})
            row['score']+=scores[researcher['id']]
            row['evidence']=sorted(set(row['evidence']+evidence.get(researcher['id'],[])))
    known=set(rows);nominations={}
    for path in graphs:
        graph=read_json(path)
        linked={edge[k] for edge in graph['edges'] for k in ('from','to')}
        for node in graph['nodes']:
            if node['id'] not in linked or not node.get('topic_hints'):continue
            for source in node['sources']:
                for author in source.get('authors',[]):
                    identifier=author.get('ids',{}).get('openalex')
                    if identifier and identifier not in known:
                        row=nominations.setdefault(identifier,{'id':identifier,'name':author['name'],'status':'nomination_requires_scope_and_identity_review','evidence':[]})
                        row['evidence'].append(node['id'])
    return sorted(rows.values(),key=lambda r:(-r['score'],r['name'])),list(nominations.values())

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--authors',type=int,default=20);p.add_argument('--offset',type=int,default=0);p.add_argument('--pages',type=int,default=3);p.add_argument('--graph',type=Path,action='append',default=[]);p.add_argument('--output',type=Path,required=True);p.add_argument('--offline',action='store_true');p.add_argument('--author-id',action='append',default=[]);args=p.parse_args()
    if not 1<=args.authors<=100 or not 1<=args.pages<=20 or args.offset<0:p.error('invalid bounds')
    directory=read_json(ROOT/'site/data/directory.json');authors,nominations=rank_authors(directory,args.graph)
    frontier=ROOT/'.cache/author-discovery/frontier.json'
    statepath=ROOT/'.out/scheduled-curation/state.json'
    progress=author_progress(read_json(statepath) if statepath.exists() else {},read_json(frontier) if frontier.exists() else {})
    policy=ROOT/'data/discovery_priority_v1.json'
    priority=args.author_id or ([a['openalex'] for a in read_json(policy)['authors']] if policy.exists() else [])
    missing=set(args.author_id)-{a['id'] for a in authors}
    if missing:p.error('Author ID lacks a linked relevant-paper identity: '+','.join(sorted(missing)))
    selected=select_authors(authors,priority,progress,args.authors,args.offset,args.author_id)
    graph=CandidateGraph(directory);client=MetadataClient(ROOT/'.cache/author-discovery',offline=args.offline)
    for author in selected:
        start=progress.get(author['id'],{}).get('next_cursor') or '*'
        collect(client,graph,'openalex','author:'+author['id'],{'filter':f'authorships.author.id:{author["id"]},is_retracted:false','sort':'publication_date:desc'},args.pages,start_cursor=start)
        coverage=graph.coverage[-1]
        coverage['rechecked_completed_author']=progress.get(author['id'],{}).get('complete',False)
        progress[author['id']]={'complete':coverage.get('complete',False),'next_cursor':coverage.get('next_cursor',start),
          'last_status':coverage['status'],'last_report':str(args.output),'basis':'actual_cursor_response'}
        if not args.offline:write_json(frontier,progress)
        result=graph.snapshot();result['author_frontier']=authors;result['nominated_authors']=nominations
        result['selected_authors']=selected;result['author_progress']=progress
        write_json(args.output,result);print(author['name'],len(graph.nodes),flush=True)
    if not selected:
        result=graph.snapshot();result.update(author_frontier=authors,nominated_authors=nominations,selected_authors=[],author_progress=progress)
        write_json(args.output,result)
if __name__=='__main__':main()
