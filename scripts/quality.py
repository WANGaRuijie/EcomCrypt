"""Conservative editorial policy, separate from bibliographic verification and scope."""
import re
from pathlib import Path
from directory import read_json

ROOT=Path(__file__).resolve().parents[1]
def normalized(text):return re.sub(r'[^a-z0-9]+',' ',text.lower()).strip()
def assess(record):
    policy=read_json(ROOT/'data/quality_policy_v1.json')
    for item in policy.get('paper_overrides',[]):
        if item.get('doi') and item['doi']==record.get('doi'):return item
        if item.get('source_ids') and any(record.get('source_ids',{}).get(k)==v for k,v in item['source_ids'].items()):return item
    venue=normalized(record.get('accepted_venue') or record.get('venue') or '')
    if record.get('is_retracted') is True:return {'decision':'exclude','reason':'source-reported retraction'}
    from venue_policy import classify
    verdict=classify(record)
    if verdict['decision']=='deny':return {'decision':'exclude','reason':verdict['reason'],'rule':verdict.get('rule')}
    for item in policy['overrides']:
        if venue==normalized(item['venue']):return item
    if record.get('kind')=='preprint' or any(x in venue for x in ('arxiv','eprint','ssrn')):
        return {'decision':'review','reason':'Preprints need substantive editorial review; author/citation links are discovery signals only.'}
    registry=read_json(ROOT/'data/venue_registry_v1.json')['venues']
    for row in sorted(registry,key=lambda r:-len(r['name'])):
        names=[normalized(s) for s in [row['name'],row['label'],*row['aliases']]]
        if venue and any(venue==name or (len(name)>15 and name in venue) for name in names):
            return {'decision':'priority' if row['priority']=='core' else 'review',
                    'reason':'Configured priority venue; still needs scope and contribution review.' if row['priority']=='core' else 'Targeted venue, requires editorial contribution review.',
                    'venue_id':row['id']}
    return {'decision':'review','reason':'Venue not resolved to a reviewed source; no automatic adoption.'}
