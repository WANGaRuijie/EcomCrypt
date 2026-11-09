import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from author_discovery import author_progress,select_authors

class AuthorDiscoveryTests(unittest.TestCase):
 def test_explicit_completed_author_recheck_never_substitutes_other_authors(self):
  self.assertEqual(select_authors([{'id':'A1'},{'id':'A2'}],[],{'A1':{'complete':True}},2,requested_ids=['A1']),[{'id':'A1'}])
 def test_visited_incomplete_author_is_resumed_before_new_ranked_author(self):
  ranked=[{'id':'A1'},{'id':'A2'},{'id':'A3'},{'id':'A4'}]
  p=author_progress({'processed_author_ids':['A1','A2'],'discovery_lane_cursors':{'author:A2':'second-page'}},{})
  self.assertTrue(p['A1']['complete']);self.assertFalse(p['A2']['complete'])
  self.assertEqual([a['id'] for a in select_authors(ranked,['A4'],p,2,2)],['A4','A2'])
 def test_saved_terminal_response_overrides_old_state_cursor(self):
  p=author_progress({'processed_author_ids':['A1'],'discovery_lane_cursors':{'author:A1':'old'}},{'A1':{'complete':True,'next_cursor':None}})
  self.assertEqual(select_authors([{'id':'A1'},{'id':'A2'}],['A1'],p,2),[{'id':'A2'}])
