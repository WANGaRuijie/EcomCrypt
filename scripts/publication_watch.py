"""Inspect configured recent proceedings; stage exact-title/byline publication upgrades."""
import argparse, hashlib, re, time
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import urlopen, Request
from concurrent.futures import ThreadPoolExecutor
from directory import read_json, write_json
from metadata import normalize_title
from harvest import CandidateGraph

ROOT=Path(__file__).resolve().parents[1]
class Page(HTMLParser):
    def __init__(self,text):
        super().__init__();self.meta={};self.text=[];self.feed(text)
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='meta' and a.get('name','').startswith('citation_'):self.meta.setdefault(a['name'],[]).append(a.get('content',''))
    def handle_data(self,data):
        if data.strip():self.text.append(data.strip())

def fetch(url,refresh=False):
    cache=ROOT/'.cache/proceedings'/ (hashlib.sha256(url.encode()).hexdigest()+'.html')
    if cache.exists() and not refresh:return cache.read_text(encoding='utf-8')
    with urlopen(Request(url,headers={'User-Agent':'ResearchDirectory/1.0'}),timeout=20) as response:raw=response.read(5_000_000).decode()
    if '<html' not in raw.lower():raise ValueError('invalid publisher page')
    cache.parent.mkdir(parents=True,exist_ok=True);cache.write_text(raw,encoding='utf-8');time.sleep(.25);return raw

def parse(url):
    p=Page(fetch(url));m=p.meta
    if not m.get('citation_doi') or not m.get('citation_author'):return None
    value=lambda k:m.get('citation_'+k,[''])[0]
    if value('title').startswith('Front Matter'):return None
    names=[' '.join(reversed(n.split(', ',1))) if ', ' in n else n for n in m['citation_author']]
    text='\n'.join(p.text);abstract=text.split('\nAbstract\n')[-1].split('\nCite As')[0][:5000] if '\nAbstract\n' in text else ''
    return {'source':'publisher','source_id':url,'source_url':url,'title':value('title'),'doi':value('doi').lower(),
      'year':int(value('date')[:4]),'venue':value('conference_title'),'kind':'conference-paper','url':url,
      'authors':[{'name':n,'ids':{},'institutions':[]} for n in names],'abstract':abstract,'related_dois':[],'is_retracted':False}

def main():
    a=argparse.ArgumentParser();a.add_argument('--volume',action='append');a.add_argument('--discover-latest',action='store_true');a.add_argument('--springer-only',action='store_true');a.add_argument('--output',type=Path,default=ROOT/'.out/recent-proceedings/graph.json');args=a.parse_args()
    config=read_json(ROOT/'data/proceedings_watch_config_v1.json')
    if not args.volume:args.volume=config['volume_ids']
    if args.springer_only and not args.discover_latest:a.error('--springer-only requires --discover-latest')
    if args.discover_latest:
        from springer_proceedings import collect as collect_springer
        records,coverage=collect_springer(config.get('springer_books',[]),fetch,args.output.with_name(args.output.stem+'-springer-toc.json'))
        if args.springer_only:return
    if args.discover_latest:
        for conference in ('AFT','ITCS'):
            try:
                html=fetch('https://drops.dagstuhl.de/entities/conference/'+conference,refresh=True)
                volumes=list(dict.fromkeys(re.findall(r'/entities/volume/LIPIcs-volume-(\d+)',html)))[:3]
                args.volume=list(dict.fromkeys([*args.volume,*volumes]))
            except Exception as e:print('index_unavailable',conference,type(e).__name__,flush=True)
    directory=read_json(ROOT/'site/data/directory.json');graph=CandidateGraph(directory);upgrades=read_json(ROOT/'data/publication_watch_v1.json') if (ROOT/'data/publication_watch_v1.json').exists() else {'records':{},'coverage':[]}
    for volume in args.volume:
        if not re.fullmatch(r'\d+',volume):raise ValueError('invalid volume ID')
        url='https://drops.dagstuhl.de/entities/volume/LIPIcs-volume-'+volume
        try:
            html=fetch(url);links=sorted(set(re.findall(r'https://drops\.dagstuhl\.de/entities/document/10\.4230/LIPIcs\.[A-Za-z]+\.\d{4}\.\d+',html)))
            if not links:raise ValueError('No proceedings links; possible incomplete or challenge page')
            with ThreadPoolExecutor(max_workers=3) as pool:records=list(pool.map(parse,links))
            for record in filter(None,records):
                graph.add(record,'proceedings:'+url)
                for paper in directory['papers']:
                    if normalize_title(paper['title'])!=normalize_title(record['title']):continue
                    if [normalize_title(n) for n in paper['authors']] != [normalize_title(a['name']) for a in record['authors']]:continue
                    if paper.get('doi')==record['doi'] and paper.get('formal_publication'):continue
                    upgrades['records'].setdefault(paper['id'],{})[record['doi']]=record
            coverage={'url':url,'status':'ok','records':sum(r is not None for r in records),'pages_checked':len(links)}
        except Exception as e:coverage={'url':url,'status':'unavailable','reason':type(e).__name__}
        graph.coverage.append(coverage);upgrades['coverage'].append(coverage);print(coverage,flush=True)
        write_json(args.output,graph.snapshot());write_json(ROOT/'data/publication_watch_v1.json',upgrades)
    print('work upgrades',len(upgrades['records']))
if __name__=='__main__':main()
