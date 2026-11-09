import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import bibliography_sweep
from directory import read_json,write_json


class BibliographySweepTests(unittest.TestCase):
    def test_idless_publication_bylines_are_not_lost_from_author_census(self):
        directory = {'researchers': [], 'papers': [
            {'id': 'p1', 'authors': ['Bo Li'], 'researcher_ids': [],
             'author_credits': [{'name': 'Bo Li', 'researcher_id': None}]},
            {'id': 'p2', 'authors': ['Bo Li'], 'researcher_ids': [],
             'author_credits': [{'name': 'Bo Li', 'researcher_id': None}]}]}
        authors, unlinked = bibliography_sweep.roster(directory)
        self.assertEqual(authors, [])
        self.assertEqual({r['work_id'] for r in unlinked}, {'p1', 'p2'})
        self.assertEqual(len({r['id'] for r in unlinked}), 2)
        self.assertTrue(all(r['entry_kind'] == 'unlinked_byline' for r in unlinked))
        self.assertEqual(unlinked, bibliography_sweep.roster(directory)[1])

    def test_unfiltered_group_resumes_and_does_not_mark_partial_response_complete(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            root=Path(folder);out=root/'report'
            write_json(root/'site/data/directory.json',{'papers':[{'id':'gs-001','title':'Seed',
                'topic_ids':['tfm'],'researcher_ids':['r1','r2']}],
                'researchers':[{'id':'r'+str(i),'name':'Author '+str(i),'identity_ids':{'openalex':'A'+str(i)}} for i in [1,2]]})
            write_json(root/'.out/scheduled-curation/state.json',{})
            frontier=root/'.cache/author-discovery/frontier.json';write_json(frontier,{})
            calls=[]
            def collect(client,graph,source,lane,params,pages,**kwargs):
                calls.append((params,kwargs))
                complete=len(calls)==2
                graph.coverage.append({'status':'ok','pages':1,'records':0,
                    'next_cursor':None if complete else 'second-page','complete':complete})
            argv=['sweep','--max-pages','1','--output-dir',str(out)]
            with patch.object(bibliography_sweep,'ROOT',root),patch.object(bibliography_sweep,'collect',collect),patch.object(sys,'argv',argv):
                bibliography_sweep.main()
                self.assertEqual(read_json(frontier),{})
                bibliography_sweep.main()
                self.assertTrue(all(p['complete'] for p in read_json(frontier).values()))
                bibliography_sweep.main()
            self.assertEqual(len(calls),2)
            self.assertEqual(calls[1][1]['start_cursor'],'second-page')
            self.assertEqual(calls[0][0]['filter'],'authorships.author.id:A1|A2,is_retracted:false')
            self.assertNotIn('search',calls[0][0])
            self.assertEqual(read_json(out/'manifest.json')['complete_authors'],2)
