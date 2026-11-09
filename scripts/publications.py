"""Project source-backed publication upgrades and retain preprint evidence."""
import hashlib
from copy import deepcopy
from directory import _link_authors

def apply_watch(directory, watch):
    for paper in directory['papers']:
        for doi,record in watch.get('records',{}).get(paper['id'],{}).items():
            if doi in {p.get('doi') for p in paper.get('publications',[])} or (doi==paper.get('doi') and paper.get('formal_publication')):continue
            if any(p['id']!=paper['id'] and doi in {v.get('doi') for v in [p,*p.get('publications',[])]} for p in directory['papers']):continue
            metadata=deepcopy(record);metadata['source_ids']={'publisher':record['source_url']}
            identities={c['name']:c.get('researcher_id') for c in paper['author_credits']}
            researchers={r['id']:r for r in directory['researchers']}
            for author in metadata['authors']:
                r=researchers.get(identities.get(author['name']))
                if r:author['ids']=r['identity_ids']
            key=paper['id']+'-edition-'+hashlib.sha256(doi.encode()).hexdigest()[:12]
            authors,ids,credits=_link_authors(directory,paper['id'],metadata,key)
            edition={k:metadata.get(k) for k in ['title','doi','year','venue','url','kind','source_ids']}
            edition.update(authors=authors,researcher_ids=ids,author_credits=credits,venue_source=record['source_url'])
            if not paper.get('formal_publication'):
                old={k:paper.get(k) for k in ['title','doi','year','venue','url','kind','source_ids']}
                if doi==old.get('doi'):
                    paper.setdefault('publication_corrections',[]).append(old)
                    edition['source_ids']={**old.get('source_ids',{}),**edition['source_ids']}
                else:paper['versions'].append(old)
                paper.update(edition,formal_publication=True,status='verified')
            else:paper.setdefault('publications',[]).append({**edition,'id':key})
