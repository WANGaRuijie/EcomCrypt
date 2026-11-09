"""Cache and parse the official arXiv Atom API, prioritizing cs.GT discovery."""
import argparse
import hashlib
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from directory import read_json, write_json
from harvest import CandidateGraph
from metadata import normalize_doi

ROOT = Path(__file__).resolve().parents[1]
NS = {'a': 'http://www.w3.org/2005/Atom', 'x': 'http://arxiv.org/schemas/atom'}

def parse_feed(raw):
    root = ET.fromstring(raw)
    records = []
    for entry in root.findall('a:entry', NS):
        text = lambda tag: ' '.join((entry.findtext(tag, default='', namespaces=NS)).split())
        url = text('a:id').replace('http://', 'https://')
        identifier = re.sub(r'v\d+$', '', url.rsplit('/abs/', 1)[-1])
        if not re.fullmatch(r'(?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})', identifier):
            continue
        doi = normalize_doi(text('x:doi'))
        records.append({'source':'arxiv', 'source_id':identifier, 'title':text('a:title'),
            'year':int(text('a:published')[:4]), 'venue':'arXiv', 'kind':'preprint',
            'doi':None, 'published_doi':doi, 'related_dois':[doi] if doi else [],
            'url':'https://arxiv.org/abs/'+identifier, 'source_url':'https://arxiv.org/abs/'+identifier,
            'abstract':text('a:summary')[:5000],
            'is_retracted': bool(re.search(r'\bwithdrawn\b', text('x:comment')+' '+text('a:title')+' '+text('a:summary'),re.I)),
            'authors':[{'name':' '.join(a.findtext('a:name',default='',namespaces=NS).split()),'ids':{},'institutions':[]}
                       for a in entry.findall('a:author',NS)],
            'categories':[c.get('term') for c in entry.findall('a:category',NS)],
            'journal_ref':text('x:journal_ref')})
    return records

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--query',default='cat:cs.GT')
    p.add_argument('--pages',type=int,default=10)
    p.add_argument('--start',type=int,default=0)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if not 1<=args.pages<=30 or args.start<0: p.error('invalid bounds')
    graph=CandidateGraph(read_json(ROOT/'site/data/directory.json'))
    cache=ROOT/'.cache/arxiv'; cache.mkdir(parents=True,exist_ok=True)
    for page in range(args.pages):
        params={'search_query':args.query,'start':args.start+page*100,'max_results':100,
                'sortBy':'submittedDate','sortOrder':'descending'}
        url='https://export.arxiv.org/api/query?'+urlencode(params)
        file=cache/(hashlib.sha256(url.encode()).hexdigest()+'.xml')
        lane={'lane':f'arxiv:{args.query}:{params["start"]}','query_url':url,'complete':False}
        try:
            if file.exists(): raw=file.read_bytes()
            else:
                with urlopen(Request(url,headers={'User-Agent':'EconCS-Directory/1.0'}),timeout=30) as response:
                    raw=response.read(4_000_001)
                if len(raw)>4_000_000: raise ValueError('response too large')
                parse_feed(raw)
                file.write_bytes(raw)
                time.sleep(3)
            records=parse_feed(raw)
            retrieved_at=datetime.fromtimestamp(file.stat().st_mtime,timezone.utc).isoformat()
            for record in records:
                graph.add({**record,'query_url':url,'retrieved_at':retrieved_at},lane['lane'])
            lane['retrieved_at']=retrieved_at
            lane.update(status='ok',records=len(records),complete=len(records)<100)
        except Exception as error:
            lane.update(status='unavailable',reason=f'http_{error.code}' if hasattr(error,'code') else type(error).__name__)
        graph.coverage.append(lane)
        write_json(args.output,graph.snapshot())
        print(lane,flush=True)
        if lane['status']!='ok' or lane['complete']: break

if __name__=='__main__': main()
