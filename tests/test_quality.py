import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from quality import assess
from author_discovery import rank_authors
class QualityTests(unittest.TestCase):
 def test_primary_publication_date_hold_does_not_label_source_quality(self):
  result=assess({'doi':'10.21428/58320208.9ce1cd26','venue':'Cryptoeconomic Systems','status':'verified'})
  self.assertEqual(result['decision'],'review')
  self.assertEqual(result['review_stage'],'metadata')
  self.assertEqual(result['quality_judgment'],'not_determined_by_this_hold')
 def test_user_denied_publishers_are_excluded(self):
  for record in [{'venue':'Electronics'},{'venue':'IEEE Access'},{'doi':'10.3390/math14071232','venue':'Mathematics'},
                 {'doi':'10.1155/2022/1234567','venue':'Security and Communication Networks'}]:
   self.assertEqual(assess(record)['decision'],'exclude')
  self.assertNotEqual(assess({'venue':'Mathematics of Operations Research'})['decision'],'exclude')
 def test_quality_is_not_inferred_from_bibliographic_verification(self):
  self.assertEqual(assess({'venue':'An Unknown Venue','status':'verified'})['decision'],'review')
  self.assertEqual(assess({'venue':'arXiv','kind':'preprint'})['decision'],'review')
  self.assertEqual(assess({'venue':'EC','kind':'conference-paper'})['decision'],'priority')
  self.assertEqual(assess({'venue':'EC','is_retracted':True})['decision'],'exclude')
 def test_editorially_adopted_directory_papers_can_seed_authors_despite_unknown_venue(self):
  d={'papers':[{'id':'new','venue':'Unknown','researcher_ids':['r']}],
     'researchers':[{'id':'r','name':'Test','identity_ids':{'openalex':'A1'}}]}
  authors,_=rank_authors(d)
  self.assertEqual([row['id'] for row in authors],['A1'])
  # rank_authors consumes the adopted directory, never raw candidate graphs.
  # Unknown-venue candidate authors still enter as nominations requiring review.
