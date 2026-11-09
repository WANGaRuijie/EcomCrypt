"""Run bounded author and citation discovery concurrently, then combine evidence."""
import argparse,subprocess,sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from directory import read_json,write_json
from author_discovery import rank_authors
from harvest import rank_candidates
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--authors',type=int,default=12);p.add_argument('--author-offset',type=int,default=0);p.add_argument('--seeds',type=int,default=8);p.add_argument('--seed-offset',type=int,default=0);p.add_argument('--pages',type=int,default=2);p.add_argument('--output-dir',type=Path,default=ROOT/'.out/parallel-discovery');a=p.parse_args()
 a.output_dir.mkdir(parents=True,exist_ok=True);author=a.output_dir/'authors.json';citation=a.output_dir/'citations.json'
 commands=[[sys.executable,str(ROOT/'scripts/author_discovery.py'),'--authors',str(a.authors),'--offset',str(a.author_offset),'--pages',str(a.pages),'--output',str(author)],
 [sys.executable,str(ROOT/'scripts/harvest.py'),'--from-year','2000','--to-year','2026','--resume-citations','--seed-limit',str(a.seeds),'--seed-offset',str(a.seed_offset),'--pages',str(a.pages),'--output',str(citation)]]
 with ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(lambda cmd:subprocess.run(cmd,cwd=ROOT).returncode,commands))
 if any(codes):raise SystemExit('Discovery branch failed; retained branch reports, no dataset changes.')
 left,right=read_json(author),read_json(citation);nodes={}
 for node in left['nodes']+right['nodes']:
  if node['id'] not in nodes:nodes[node['id']]=node
  else:
   old=nodes[node['id']];old['lanes']=sorted(set(old['lanes']+node['lanes']));sources={(r['source'],r['source_id']):r for r in old['sources']+node['sources']};old['sources']=list(sources.values())
 merged={'schema_version':1,'nodes':list(nodes.values()),'edges':right['edges'],'coverage':left['coverage']+right['coverage'],'anchors':right['anchors']}
 merged['review_queue']=rank_candidates(merged)
 _,nominations=rank_authors(read_json(ROOT/'site/data/directory.json'),[citation]);merged['nominated_authors']=nominations
 write_json(a.output_dir/'combined.json',merged)
 print('combined',len(nodes),'citation_edges',len(right['edges']),'nominated_authors',len(nominations))
if __name__=='__main__':main()
