"""Offline update checks. Synthetic fixtures cannot reach a release snapshot."""

from datetime import date
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from directory import append_work, new_directory, read_json, write_json
from metadata import MetadataError, reconcile
from update import Classifier, MAX_REQUEST_COST, MODEL, discover, main, screen, seed_from_record, stage_run, candidate_identity


AS_OF = date(2026, 11, 6)
FIXTURE = ROOT / "tests/fixtures/update_candidates.json"
EMPTY_LEDGER = {"schema_version": 1, "records": []}


class UpdateTests(unittest.TestCase):
    def test_archive_revision_identity_survives_title_and_openalex_id_changes(self):
        original = candidate_identity({'title':'Old title','source_ids':{'arxiv':'1911.04124'}})
        revised = candidate_identity({'title':'Different title','source':'openalex','source_id':'Wexample',
                                      'url':'https://arxiv.org/abs/1911.04124v2'})
        self.assertIn(('arxiv','1911.04124'), original & revised)
        self.assertIn(('arxiv','1911.04124'), candidate_identity({'doi':'10.48550/arXiv.1911.04124'}))

    def test_archive_identity_respects_host_and_old_style_identifiers(self):
        self.assertIn(('arxiv','cs/0608019'), candidate_identity({'url':'https://arxiv.org/pdf/cs/0608019v3.pdf'}))
        self.assertNotIn(('arxiv','1911.04124'), candidate_identity({'url':'https://arxiv.org.example/abs/1911.04124'}))
        self.assertFalse(candidate_identity({'url':'https://arxiv.org/abs/1911.04125'}) &
                         candidate_identity({'url':'https://arxiv.org/abs/1911.04124'}))

    def setUp(self):
        self.base = new_directory([{"id": "tfm", "name": "Transaction Fee Mechanisms"}, {"id": "mining", "name": "Mining"}])
        self.rows = read_json(FIXTURE)
        self.records = [row["candidate"] for row in self.rows]
        self.evidence = {row["candidate"]["source_id"]: row["evidence"] for row in self.rows}

    def verify(self, record):
        return reconcile(seed_from_record(record), [record, *self.evidence[record["source_id"]]])

    def test_verified_unknown_venue_requires_editorial_review(self):
        def verify(record):
            result=self.verify(record)
            result['metadata']['venue']='Unreviewed Venue'
            return result
        staged,decisions,accepted=screen(self.base,[self.records[0]],verify,as_of=AS_OF,days=45)
        self.assertEqual(decisions[0]['status'],'review_quality')
        self.assertEqual(accepted,[])

    def test_only_corroborated_rules_enter_append_only_projection(self):
        good, partial = self.records
        records = [good, good, partial, partial, {**good, "is_retracted": True}, {**good, "kind": "preprint"}]
        staged, decisions, accepted = screen(self.base, records, self.verify, as_of=AS_OF, days=45)
        self.assertEqual([row["status"] for row in decisions], [
            "accepted", "duplicate_directory", "review_metadata", "duplicate_discovery",
            "retracted_or_unknown", "invalid_candidate",
        ])
        self.assertEqual(len(staged["papers"]), 1)
        self.assertEqual(staged["papers"][0]["topic_ids"], ["tfm"])
        self.assertEqual(accepted[0]["verification"]["status"], "verified")
        self.assertEqual(self.base["papers"], [])

    def test_duplicate_existing_version_is_never_added(self):
        original, _ = self.records
        append_work(
            self.base, work_id="seed-work", topic_ids=["tfm"], raw_input={"title": "Related title"},
            verification={
                "status": "partial", "metadata": {"title": "Related title"},
                "versions": [{"title": "Alias", "source_ids": {"openalex": original["source_id"]}}],
            },
        )
        staged, decisions, _ = screen(self.base, [original], self.verify, as_of=AS_OF, days=45)
        self.assertEqual(staged, self.base)
        self.assertEqual(decisions[0]["status"], "duplicate_directory")

    def test_fixture_can_write_only_a_report(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            output = Path(temp)
            base = output / "base.json"
            write_json(base, self.base)
            result = main([
                "--candidates", str(FIXTURE), "--base", str(base), "--ledger", str(output / "ledger.json"),
                "--as-of", str(AS_OF), "--output-dir", str(output),
            ])
            self.assertEqual(result, 0)
            self.assertEqual(read_json(output / "report.json")["counts"], {"accepted": 1, "review_metadata": 1})
            self.assertFalse((output / "current.json").exists())

    def test_failed_provider_retains_previous_release(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            output = Path(temp)
            options = {"as_of": AS_OF, "days": 45, "dry_run": False, "fixture": False, "classifier": None}
            stage_run(self.base, EMPTY_LEDGER, output, self.records, self.verify, **options)
            previous = read_json(output / "current.json")
            release = output / previous["release"]
            old_directory = read_json(release / "directory.json")
            old_ledger = read_json(release / "accepted_updates_v1.json")
            self.assertEqual(len(old_ledger["records"]), 1)
            self.assertEqual(old_ledger["records"][0]["work_id"], old_directory["papers"][0]["id"])
            fail = Mock(return_value={"queries": [
                {"source": "dblp", "status": "unavailable"},
                {"source": "crossref", "status": "unavailable"},
            ]})
            with self.assertRaises(MetadataError):
                stage_run(self.base, EMPTY_LEDGER, output, self.records, fail, **options)
            self.assertEqual(read_json(output / "current.json"), previous)
            self.assertEqual(read_json(release / "directory.json"), old_directory)
            stage_run(old_directory, old_ledger, output, [], self.verify, **options)
            self.assertEqual(read_json(output / "current.json"), previous)

    def test_available_independent_provider_can_corroborate(self):
        good = {**self.records[0], "kind": "conference-paper"}
        result = self.verify(good)
        result["queries"] = [
            {"source": "crossref", "status": "unavailable"},
            {"source": "dblp", "status": "ok"},
        ]
        _, decisions, _ = screen(self.base, [good], Mock(return_value=result), as_of=AS_OF, days=45)
        self.assertEqual(decisions[0]["status"], "accepted")

    def test_discovery_watchlist_is_bounded_and_uses_verified_authors(self):
        directory = {**self.base, "researchers": [
            {"id": "r1", "identity_ids": {"openalex": "A1"}},
            {"id": "r2", "identity_ids": {"openalex": "A2"}},
        ], "papers": [
            {"status": "verified", "researcher_ids": ["r1"]},
            {"status": "partial", "researcher_ids": ["r2"]},
        ]}
        client = Mock()
        client.search_openalex.return_value = self.records * 20
        results = discover(client, directory, AS_OF, 45)
        self.assertEqual(len(results), 56)
        self.assertEqual(results[6]["discovery_lane"], "verified-author-watchlist")
        params = client.search_openalex.call_args.args[0]
        self.assertTrue(params["filter"].endswith(",author.id:A1"))

    def test_failed_release_commit_retains_previous_pointer(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            output = Path(temp)
            options = {"as_of": AS_OF, "days": 45, "dry_run": False, "fixture": False, "classifier": None}
            stage_run(self.base, EMPTY_LEDGER, output, [], self.verify, **options)
            previous = read_json(output / "current.json")

            def fail_on_ledger(path, value):
                if path.name == "accepted_updates_v1.json":
                    raise OSError("simulated write failure")
                write_json(path, value)

            with patch("update.write_json", side_effect=fail_on_ledger), self.assertRaises(OSError):
                stage_run(self.base, EMPTY_LEDGER, output, self.records, self.verify, **options)
            self.assertEqual(read_json(output / "current.json"), previous)

    def test_llm_label_cannot_promote_weak_title(self):
        record = {**self.records[0], "title": "Blockchain in Practice"}
        classifier = Mock()
        classifier.classify.return_value = {"status": "classified", "topic": "tfm"}
        verify = Mock()
        staged, decisions, accepted = screen(self.base, [record], verify, as_of=AS_OF, days=45, classifier=classifier)
        self.assertEqual(decisions[0]["status"], "review_scope")
        self.assertEqual(staged, self.base)
        self.assertEqual(accepted, [])
        verify.assert_not_called()


class ClassifierTests(unittest.TestCase):
    def test_unknown_usage_keeps_reservation_and_prevents_second_request(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            send = Mock(side_effect=TimeoutError)
            classifier = Classifier(Path(temp), "test-key", 100, send)
            topics = {"tfm": "Fees"}
            self.assertEqual(classifier.classify("First", topics)["status"], "request_failed")
            self.assertEqual(classifier.charged_upper_bound, MAX_REQUEST_COST)
            self.assertEqual(classifier.classify("Second", topics)["status"], "budget_exhausted")
            send.assert_called_once()

    def test_reuses_validated_result_without_new_call(self):
        reply = {
            "model": MODEL, "service_tier": "default", "status": "completed",
            "usage": {"input_tokens": 250, "output_tokens": 12},
            "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps({"topic": "tfm"})}]}],
        }
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            cache = Path(temp)
            send = Mock(return_value=reply)
            classifier = Classifier(cache, "test-key", 100, send)
            topics = {"tfm": "Fees"}
            self.assertEqual(classifier.classify("Blockchain", topics)["status"], "classified")
            self.assertLess(classifier.charged_upper_bound, MAX_REQUEST_COST)
            offline = Classifier(cache, None, 0, send)
            self.assertEqual(offline.classify("Blockchain", topics), {"status": "cached", "topic": "tfm"})
            send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
