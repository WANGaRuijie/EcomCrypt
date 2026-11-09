import sys,unittest
from pathlib import Path
from copy import deepcopy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from directory import new_directory,append_work,validate_directory
from publications import apply_watch

class PublicationTests(unittest.TestCase):
 def test_published_version_replaces_preprint_without_losing_history_or_identity(self):
  directory=new_directory([{'id':'amm','name':'AMM'}])
  metadata={'title':'Liquidity','authors':[{'name':'Alice Example','ids':{'openalex':'A1'}}],
    'year':2024,'venue':'arXiv','kind':'preprint','doi':None,'source_ids':{'arxiv':'2401.12345'}}
  append_work(directory,work_id='paper',topic_ids=['amm'],verification={'status':'verified','metadata':metadata},raw_input={'title':'Liquidity'})
  record={**metadata,'doi':'10.1234/formal','kind':'conference-paper','venue':'AFT','year':2025,'source_url':'https://example.org/proceedings'}
  watch={'records':{'paper':{'10.1234/formal':record}}}
  apply_watch(directory,watch);paper=directory['papers'][0]
  self.assertTrue(paper['formal_publication']);self.assertEqual(paper['year'],2025)
  self.assertEqual(paper['versions'][0]['source_ids'],{'arxiv':'2401.12345'})
  before=deepcopy(directory);apply_watch(directory,watch);self.assertEqual(directory,before)
  validate_directory(directory)

 def test_same_formal_doi_with_wrong_preprint_type_is_corrected(self):
  directory=new_directory([{'id':'amm','name':'AMM'}])
  metadata={'title':'Liquidity','authors':[{'name':'Alice Example','ids':{}}], 'year':2024,'venue':'arXiv','kind':'preprint','doi':'10.1234/formal','source_ids':{'openalex':'W1'}}
  append_work(directory,work_id='paper',topic_ids=['amm'],verification={'status':'verified','metadata':metadata},raw_input={'title':'Liquidity'})
  record={**metadata,'kind':'conference-paper','venue':'AFT','source_url':'https://example.org/proceedings'}
  apply_watch(directory,{'records':{'paper':{'10.1234/formal':record}}})
  paper=directory['papers'][0]
  self.assertTrue(paper['formal_publication'])
  self.assertEqual(paper['source_ids']['openalex'],'W1')
  self.assertEqual(len(paper['publication_corrections']),1)
