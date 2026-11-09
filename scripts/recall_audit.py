"""Rescue unresolved historic screens into a persistent evidence queue; no paid calls or adoption."""
import argparse
from collections import Counter
from pathlib import Path
from directory import read_json, write_json
from expand import abstract_text, editorial_scope_review
from evidence_review import evidence_review, prefer_abstract, retain_editorial_followup
from update import work_identity
from metadata import _openalex_record

ROOT = Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'.out/recall-audit-2026-11-07/audit.json')
    a=p.parse_args()
    state=read_json(ROOT/'.out/scheduled-curation/state.json')
    paths=[ROOT/'.out/parallel-discovery/combined.json',ROOT/'.out/author-first/pilot.json']
    paths += [ROOT/x for x in state.get('discovery_graph_paths',[])]
    paths += list((ROOT/'.out').glob('corpus-*/graph.json'))
    paths += [ROOT/'.out/deepseek-harvest/graph.json',ROOT/'.out/recent-proceedings/graph.json']
    sources={};abstracts={};history={}
    for path in dict.fromkeys(paths):
        if not path.exists():continue
        for node in read_json(path)['nodes']:
            for raw in node['sources']:
                identifier=raw['source_id'];sources.setdefault(identifier,raw)
                abstracts[identifier]=prefer_abstract(abstracts.get(identifier),raw.get('abstract'))
    # Expand requests store public credential-free envelopes; reuse exact provider evidence.
    for path in (ROOT/'.cache/expand/metadata').glob('*.json'):
        payload=read_json(path).get('payload',{})
        for raw in payload.get('results',[]):
            if not isinstance(raw,dict) or not isinstance(raw.get('id'),str):continue
            identifier=raw['id'].rsplit('/',1)[-1]
            abstracts[identifier]=prefer_abstract(abstracts.get(identifier),abstract_text(raw.get('abstract_inverted_index')))
            if raw.get('title') and raw.get('authorships'):
                sources.setdefault(identifier,_openalex_record(raw))
    reports=list((ROOT/'data').glob('discovery_campaign_v*.json'))+sorted((ROOT/'.out/scheduled-curation').glob('round-*/screen.json'))
    for path in reports:
        doc=read_json(path)
        for row in doc.get('records',doc.get('rows',[])):
            identifier=row.get('classification',{}).get('id')
            if identifier:
                history.setdefault(identifier,[]).append({'report':str(path.relative_to(ROOT)), 'row':row})
                evidence=row.get('evidence_input',{})
                if evidence.get('raw_input'):sources.setdefault(identifier,evidence['raw_input'])
                if row.get('raw_input'):sources.setdefault(identifier,row['raw_input'])
                abstracts[identifier]=prefer_abstract(abstracts.get(identifier),evidence.get('abstract'))
    existing=set().union(*(work_identity(x) for x in read_json(ROOT/'site/data/directory.json')['papers']))
    queuepath=ROOT/'.out/evidence-review/queue.json'
    previous=read_json(queuepath) if queuepath.exists() else {'records':[]}
    previous_by_id={row['id']:row for row in previous['records']}
    decisions={**previous.get('editorial_resolutions',{}),
               **{r['id']:r['editorial_resolution'] for r in previous['records'] if r.get('editorial_resolution')}}
    queue=[];counts=Counter();missing=[]
    for identifier,observations in history.items():
        row=observations[-1]['row'];label=row['classification']
        source=sources.get(identifier)
        if source is None:
            source={'title':row.get('title',''),'doi':row.get('doi'),'source_id':identifier,
                    'source':'unknown', 'original_record_missing':True,
                    'reconstructed_from_screen_report':observations[-1]['report']}
            missing.append(identifier)
        prior=previous_by_id.get(identifier,{})
        followup=retain_editorial_followup(prior,evidence_review(source,label,abstracts.get(identifier,'')))
        if not followup:continue
        counts['flagged_historical_ids']+=1
        if work_identity(source)&existing:
            counts['already_adopted_or_versioned']+=1;continue
        hold=editorial_scope_review(source)
        if hold and hold['decision']=='exclude':counts['editorial_excluded']+=1;continue
        queue.append({'id':identifier,'raw_input':source,'abstract':abstracts.get(identifier,''),
            'followup':followup,'classification_history':observations,'editorial_hold':hold,
            'editorial_resolution':decisions.get(identifier),
            'status':'resolved' if decisions.get(identifier) else 'review_evidence',
            'editorial_review_required':prior.get('editorial_review_required',False),
            'evidence_recovery_history':prior.get('evidence_recovery_history',[])})
    from evidence_review import intersection_title
    from quality import assess
    for row in queue:
        row['title_intersection_signal']=intersection_title(row['raw_input'].get('title',''))
        row['priority_venue']=assess(row['raw_input'])['decision']=='priority'
    queue.sort(key=lambda r:(not r['title_intersection_signal'],not r['priority_venue'],r['id']))
    write_json(queuepath,{'schema_version':1,'policy':'No automatic adoption. Historic processed IDs remain intact; this independent evidence-review lane is not suppressed by discovery dedup.', 'records':queue,'editorial_resolutions':decisions})
    counts.update(review_queue=len(queue),historical_source_ids=len(history),without_original_graph_source=len(missing),
                  intersection_title_signals=sum(r['title_intersection_signal'] for r in queue))
    write_json(a.output,{'counts':dict(counts),'queue_path':str(queuepath),'missing_source_ids':missing,
        'root_causes':['Abstract-only evidence requirement plus missing/short abstracts.',
        'Exact excerpt validation failures require evidence recovery, not terminal screening.',
        'Historic screened IDs suppressed unresolved candidates on later discovery.',
        'Author roster wrongly excluded accepted papers outside priority venues.'],
        'automatic_adoptions':0,'paid_calls':0})
    print(dict(counts))


if __name__=='__main__':main()
