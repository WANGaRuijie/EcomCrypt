import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from topics import annotate
class TopicTests(unittest.TestCase):
 def test_specific_economic_topics_replace_the_old_catch_all(self):
  p={'title':'Tokenomics, monetary policy and the cost of attack','topic_ids':['economics']}
  annotate(p)
  self.assertNotIn('economics',p['topic_ids'])
  self.assertIn('tokenomics',p['topic_ids'])
  self.assertIn('economic-security',p['topic_ids'])
 def test_governance_requires_strategic_evidence(self):
  p={'title':'Blockchain Governance: An Overview','topic_ids':['economics']};annotate(p)
  self.assertNotIn('governance',p['topic_ids'])
  annotate(p,'We characterize Nash equilibrium in token voting.')
  self.assertIn('governance',p['topic_ids'])
 def test_multiple_explicit_topics_and_evidence(self):
  p={'title':'MEV and transaction ordering in Uniswap automated market makers','topic_ids':['amm']}
  annotate(p);self.assertEqual(set(p['topic_ids']),{'amm','defi','mev'})
  self.assertTrue(all(e['excerpt'] for e in p['topic_annotations']))
 def test_no_unrelated_topic_inference(self):
  p={'title':'Secure computation','topic_ids':['rational-cryptography']};annotate(p)
  self.assertEqual(p['topic_ids'],['rational-cryptography'])
