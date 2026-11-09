import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from expand import BUDGET, abstract_text, classify, verify_candidate, editorial_scope_review
from campaign_budget import CampaignBudget


class ExpansionTests(unittest.TestCase):
    def test_editorial_scope_matches_source_or_reconciled_doi_but_not_title(self):
        review={'decision':'exclude','doi':'10.1234/excluded','source_ids':{'openalex':'W1'},'title':'Same title'}
        policy={'records':[review]}
        self.assertEqual(editorial_scope_review({'source':'openalex','source_id':'W1'},policy),review)
        self.assertEqual(editorial_scope_review({'doi':'https://doi.org/10.1234/EXCLUDED'},policy),review)
        self.assertIsNone(editorial_scope_review({'title':'Same title','doi':'10.1234/different'},policy))

    def test_editorial_scope_holds_cannot_authorize_adoption(self):
        policy={'records':[{'doi':'10.1234/held','decision':'review'},
                           {'doi':'10.1234/allowed','decision':'allow'}]}
        self.assertEqual(editorial_scope_review({'doi':'10.1234/held'},policy)['decision'],'review')
        self.assertIsNone(editorial_scope_review({'doi':'10.1234/allowed'},policy))

    def test_missing_model_row_is_reviewed_without_losing_the_batch(self):
        response=MagicMock()
        response.__enter__.return_value.read.return_value=json.dumps({'usage':{'prompt_tokens':10,'completion_tokens':10},'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'results':[]})}}]})
        with tempfile.TemporaryDirectory(dir=ROOT) as folder, patch('expand.build_opener') as opener:
            opener.return_value.open.return_value=response
            rows,cost,_=classify([{'id':'W1','abstract':'Blockchain mechanism'}],{'tfm':'TFM'},'test-key',Path(folder),0)
            self.assertEqual(rows[0]['decision'],'uncertain')
            self.assertEqual(rows[0]['id'],'W1')
            self.assertGreater(cost,0)

    def test_arbitrary_primary_source_cannot_bypass_metadata_verification(self):
        with self.assertRaisesRegex(ValueError,'Unsupported primary'):
            verify_candidate(Mock(),{'source':'publisher','source_url':'https://example.org/fake'})

    def test_official_preprint_can_be_recorded_but_publication_hint_blocks_fallback(self):
        source={'source':'arxiv','source_id':'2601.12345','source_url':'https://arxiv.org/abs/2601.12345',
            'title':'Rational security','authors':[{'name':'Alice Example'}],'year':2026,'doi':None,
            'venue':'arXiv','kind':'preprint','url':'https://arxiv.org/abs/2601.12345'}
        client=Mock()
        client.verify.return_value={'status':'partial','metadata':None,'conflicts':[],'versions':[]}
        result=verify_candidate(client,source)
        self.assertEqual(result['verification_basis'],'primary_archive_metadata_not_peer_review')
        self.assertIsNone(result['metadata']['doi'])
        self.assertEqual(result['metadata']['source_ids'],{'arxiv':'2601.12345'})
        self.assertEqual(verify_candidate(client,{**source,'journal_ref':'EC 2026'})['status'],'partial')

    def test_no_abstract_does_not_spend_api_budget(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp, patch('expand.build_opener') as opener:
            rows,cost,_=classify([{'id':'W1','abstract':''}],{},'test-key',Path(temp),0)
            self.assertEqual(rows[0]['decision'],'uncertain')
            self.assertEqual(cost,0)
            opener.assert_not_called()

    def test_abstract_reconstruction_preserves_token_order(self):
        self.assertEqual(abstract_text({"market": [1, 3], "A": [0], "vs": [2]}), "A market vs market")

    def test_classification_caches_validated_results_and_enforces_budget(self):
        batch = [{"id": "W1", "title": "Test", "venue": "EC", "abstract": "Blockchain fee mechanism"}]
        topics = {"tfm": "Transaction fees"}
        labels = [{"id": "W1", "decision": "core", "topic": "tfm", "reason": "Tests a fee mechanism.",
                   "blockchain_evidence": "Blockchain", "economics_evidence": "fee mechanism", "scope":"blockchain_economics"}]
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            "usage": {"prompt_tokens": 400, "completion_tokens": 50},
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"results": labels})}}],
        })
        with tempfile.TemporaryDirectory(dir=ROOT) as temp, patch("expand.build_opener") as opener:
            path = Path(temp)
            opener.return_value.open.return_value = response
            with self.assertRaisesRegex(ValueError, "budget"):
                classify(batch, topics, "test-key", path, BUDGET)
            opener.assert_not_called()
            self.assertEqual(classify(batch, topics, "test-key", path, 0), (labels, 180000, False))
            self.assertEqual(classify(batch, topics, "test-key", path, 180000), (labels, 180000, True))
            self.assertEqual(opener.call_count, 1)

    def test_invented_evidence_cannot_be_core(self):
        batch = [{"id": "W1", "title": "Consensus", "venue": "FC", "abstract": "Blockchain consensus"}]
        labels = [{"id": "W1", "decision": "core", "topic": "mining", "reason": "Claimed economics",
                   "blockchain_evidence": "Blockchain", "economics_evidence": "equilibrium"}]
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            "usage": {"prompt_tokens": 400, "completion_tokens": 50},
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"results": labels})}}],
        })
        with tempfile.TemporaryDirectory(dir=ROOT) as temp, patch("expand.build_opener") as opener:
            opener.return_value.open.return_value = response
            result, _, _ = classify(batch, {"mining": "Mining"}, "test-key", Path(temp), 0)
            self.assertEqual(result[0]["decision"], "uncertain")
            self.assertEqual(result[0]["economics_evidence"], "")

    def test_campaign_persists_cost_and_reserves_unknown_billing(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            path = Path(temp) / "budget.json"
            budget = CampaignBudget(path, 100)
            token = budget.reserve("first", 60)
            with self.assertRaisesRegex(ValueError, "unknown billing"):
                CampaignBudget(path, 100).reserve("first", 60)
            budget.settle(token, 20)
            again = CampaignBudget(path, 100)
            token = again.reserve("first", 60)
            again.settle(token, 30)
            self.assertEqual(CampaignBudget(path, 100).spent, 50)
            with self.assertRaisesRegex(ValueError, "exhausted"):
                CampaignBudget(path, 100).reserve("third", 60)
