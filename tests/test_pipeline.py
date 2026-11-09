import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import monthly
import rubric
import venue_policy
from screen import run_stage, LLMError
from store import Spend, Store, aliases_for
from source_feeds import parse_eprint, parse_arxiv

FIXTURES = ROOT / 'tests/fixtures'


class FakeLLM:
    model = 'fake'

    def __init__(self, title_keep=lambda t: True, decide=None, fail_first=False):
        self.calls = 0
        self.title_keep = title_keep
        self.decide = decide or (lambda p: {'decision': 'include', 'topics': ['mining'], 'confidence': 'high',
                                            'crossing': 'blockchain_econ', 'reason': 'ok',
                                            'evidence_T': p['title'][:30], 'evidence_E': p['title'][:30]})
        self.fail_first = fail_first

    def estimate(self, system, user, max_tokens):
        return 1000

    def cost(self, usage):
        return usage['n']

    def complete(self, system, user, max_tokens):
        self.calls += 1
        if self.fail_first and self.calls == 1:
            raise LLMError('boom')
        papers = json.loads(user)['papers']
        if 'abstract' in papers[0]:
            rows = [{'id': p['id'], **self.decide(p)} for p in papers]
        else:
            rows = [{'id': p['id'], 'keep': self.title_keep(p['title']), 'code': None if self.title_keep(p['title']) else 'single_side_T'} for p in papers]
        return json.dumps({'results': rows}), 'stop', {'n': 500}


class VenuePolicyTests(unittest.TestCase):
    def test_denied_publishers_registered_venues_and_unknowns(self):
        self.assertEqual(venue_policy.classify({'doi': '10.1109/ACCESS.2023.1', 'venue': 'IEEE Access'})['decision'], 'deny')
        self.assertEqual(venue_policy.classify({'doi': '10.3390/e1', 'venue': 'Entropy'})['decision'], 'deny')
        self.assertEqual(venue_policy.classify({'doi': '10.1155/2021/1', 'venue': 'Complexity'})['decision'], 'deny')
        self.assertEqual(venue_policy.classify({'venue': 'Mathematics'})['decision'], 'deny')
        self.assertEqual(venue_policy.classify({'venue': 'Mathematics of Operations Research'})['decision'], 'allow')
        self.assertEqual(venue_policy.classify({'venue': 'CCS', 'dblp_venue': 'CCS'})['venue_id'], 'ccs')
        self.assertEqual(venue_policy.classify({'dblp_venue': 'Games Econ. Behav.'})['venue_id'], 'geb')
        self.assertEqual(venue_policy.classify({'venue': 'GameSec'})['venue_id'], 'gamesec')
        self.assertEqual(venue_policy.classify({'venue': 'CoRR', 'kind': 'preprint'})['decision'], 'preprint')
        self.assertEqual(venue_policy.classify({'venue': 'Journal of Obscure Things'})['decision'], 'unknown')

    def test_work_with_an_acceptable_formal_version_is_not_removed(self):
        denied = {'doi': '10.3390/x', 'venue': 'Electronics'}
        self.assertIsNotNone(venue_policy.work_denial(denied, []))
        self.assertIsNone(venue_policy.work_denial(denied, [{'venue': 'CCS', 'kind': 'proceedings-article'}]))
        self.assertIsNotNone(venue_policy.work_denial(denied, [{'venue': 'arXiv', 'kind': 'preprint'}]))

    def test_build_drops_denied_ledger_works(self):
        directory = json.loads((ROOT / 'site/data/directory.json').read_text(encoding='utf-8'))
        venues = {p.get('venue') for p in directory['papers']}
        self.assertFalse(venues & {'IEEE Access', 'Electronics', 'Mathematics', 'Analytics'})
        removed = json.loads((ROOT / 'data/venue_removals_v1.json').read_text(encoding='utf-8'))['removed']
        ids = {p['id'] for p in directory['papers']}
        self.assertEqual(len(removed), 6)
        self.assertFalse(ids & {r['work_id'] for r in removed})


class RubricTests(unittest.TestCase):
    def test_prefilter_recall_and_application_domain(self):
        self.assertTrue(rubric.prefilter('Selfish Mining in Ethereum')[0])
        self.assertTrue(rubric.prefilter('Rational Secret Sharing Revisited', venue_group='Security & Crypto')[0])
        self.assertTrue(rubric.prefilter('Incentive-Compatible Replication in Distributed Databases')[0])
        self.assertFalse(rubric.prefilter('Convolutional Networks for Image Segmentation')[0])
        self.assertEqual(rubric.prefilter('A Stackelberg Game for Edge Computing Offloading Security')[1], 'prefilter_application_domain')
        self.assertEqual(rubric.prefilter('Erratum: Selfish mining')[1], 'prefilter_non_research_item')
        self.assertTrue(rubric.prefilter('The Gap Game', venue_group='Blockchain')[0])

    def test_include_requires_verbatim_excerpts_and_topic(self):
        paper = {'id': 'p0', 'title': 'Bribery in PoS', 'abstract': 'We model validators as strategic agents and derive equilibria.'}
        good = rubric.validate_abstract_row({'decision': 'include', 'topics': ['pos'], 'confidence': 'high',
                                             'evidence_T': 'validators', 'evidence_E': 'derive equilibria'}, paper)
        self.assertEqual(good['decision'], 'include')
        fake = rubric.validate_abstract_row({'decision': 'include', 'topics': ['pos'], 'evidence_T': 'validators',
                                             'evidence_E': 'a quote that is not there'}, paper)
        self.assertEqual(fake['decision'], 'needs_fulltext')
        notopic = rubric.validate_abstract_row({'decision': 'include', 'topics': ['nonsense'], 'evidence_T': 'validators',
                                                'evidence_E': 'derive equilibria'}, paper)
        self.assertEqual(notopic['decision'], 'needs_fulltext')
        self.assertEqual(rubric.validate_abstract_row(None, paper)['decision'], 'needs_fulltext')


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 's.sqlite')

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_preprint_and_formal_version_are_one_work(self):
        a, new_a = self.store.add({'source': 'arxiv', 'source_id': '2301.00001v2', 'title': 'A Game-Theoretic Study of Rollup Sequencers'}, origin='arxiv')
        b, new_b = self.store.add({'source': 'dblp', 'source_id': 'journals/corr/abs-2301-00001',
                                   'doi': '10.48550/arXiv.2301.00001', 'title': 'A Game-Theoretic Study of Rollup Sequencers'}, origin='dblp')
        c, new_c = self.store.add({'source': 'openalex', 'source_id': 'W1', 'doi': '10.1145/1.2',
                                   'title': 'A game-theoretic study of rollup sequencers'}, origin='openalex')
        self.assertTrue(new_a)
        self.assertFalse(new_b or new_c)
        self.assertEqual(len({a, b, c}), 1)
        self.assertEqual(len(self.store.editions(a)), 3)

    def test_directory_status_survives_merge_and_abstract_never_shrinks(self):
        key, _ = self.store.add({'source': 'x', 'source_id': '1', 'title': 'Majority is Not Enough: Bitcoin Mining is Vulnerable'},
                                origin='legacy', abstract='long ' * 100)
        self.store.add({'source': 'directory', 'source_id': 'gs', 'doi': '10.1/abc',
                        'title': 'Majority is not enough: Bitcoin mining is vulnerable'}, origin='directory', status='in_directory')
        self.store.set_abstract(key, 'short', 'test')
        work = self.store.work(key)
        self.assertEqual(work['status'], 'in_directory')
        self.assertGreater(len(work['abstract']), 400)

    def test_aliases_ignore_arxiv_doi_as_doi(self):
        aliases = aliases_for({'doi': '10.48550/arXiv.2301.00001', 'title': 'short'})
        self.assertEqual(aliases, ['arxiv:2301.00001'])


class ScreenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 's.sqlite')
        for i in range(25):
            key, _ = self.store.add({'source': 'arxiv', 'source_id': f'2401.{i:05d}', 'title': f'Selfish mining paper number {i} in Bitcoin'},
                                    origin='t', abstract='We study selfish mining in Bitcoin and derive an equilibrium. ' * 5)
            self.store.set_status(key, 'prefilter_pass')

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_two_stages_once_per_rubric_and_budget_stops_cleanly(self):
        llm = FakeLLM(title_keep=lambda t: not t.endswith('3 in Bitcoin'))
        spend = Spend(self.store, 'r1', 1.0)
        stats = run_stage(self.store, self.store.works(['prefilter_pass']), stage='title', llm=llm, spend=spend, batch_size=10, log=lambda m: None)
        self.assertEqual(stats['requests'], 3)
        self.assertEqual(self.store.counts().get('title_drop'), 3)  # numbers 3, 13 and 23
        run_stage(self.store, self.store.works(['title_keep']), stage='abstract', llm=llm, spend=spend, batch_size=10, log=lambda m: None)
        calls = llm.calls
        run_stage(self.store, self.store.works(['screen_include', 'screen_exclude', 'needs_fulltext']), stage='abstract',
                  llm=llm, spend=spend, batch_size=10, log=lambda m: None)
        self.assertEqual(llm.calls, calls, 'already-screened works must not be re-sent')
        self.assertEqual(spend.used, llm.calls * 500)
        tight = Spend(self.store, 'r2', 0.0000015)    # room for one reservation of 1000 nanodollars
        for key in [w['key'] for w in self.store.works()][:20]:
            self.store.set_status(key, 'prefilter_pass')
        self.store.db.execute("DELETE FROM screens WHERE stage='title'")
        stats = run_stage(self.store, self.store.works(['prefilter_pass']), stage='title', llm=llm, spend=tight, batch_size=5, log=lambda m: None)
        self.assertTrue(stats['budget_stopped'])
        self.assertEqual(stats['requests'], 1)

    def test_failed_request_keeps_reservation_and_leaves_works_queued(self):
        llm = FakeLLM(fail_first=True)
        spend = Spend(self.store, 'r1', 1.0)
        run_stage(self.store, self.store.works(['prefilter_pass']), stage='title', llm=llm, spend=spend, batch_size=25, concurrency=1, log=lambda m: None)
        self.assertEqual(self.store.counts().get('prefilter_pass'), 25)
        self.assertEqual(spend.used, 1000)


class SourceParserTests(unittest.TestCase):
    def test_dblp_fixture_parses_entities_and_skips_old_and_non_records(self):
        from source_dblp import iter_records
        rows = list(iter_records(FIXTURES / 'dblp_sample.xml', min_year=2008))
        self.assertEqual([r['source_id'] for r in rows], ['conf/ccs/EyalS14', 'journals/corr/abs-2301-00001', 'journals/access/Foo23'])
        self.assertEqual(rows[0]['authors'][1]['name'], 'Emin Gün Sirer')
        self.assertEqual(rows[1]['kind'], 'preprint')
        self.assertEqual(rows[1]['title'], 'A Game-Theoretic Study of Rollup Sequencers')

    def test_eprint_and_arxiv_parsers(self):
        records, token = parse_eprint((FIXTURES / 'eprint_oai.xml').read_bytes())
        self.assertEqual(token, 'tok123')
        self.assertEqual(records[0]['source_id'], '2024/123')
        self.assertIn('rational', records[0]['abstract'])
        rows = list(parse_arxiv((FIXTURES / 'arxiv_atom.xml').read_bytes()))
        self.assertEqual(rows[0]['source_id'], '2401.01234')
        self.assertEqual(rows[0]['published_doi'], '10.1145/1234.5678')


class EndToEndTests(unittest.TestCase):
    def test_dblp_ingest_screen_promote_dry_run_and_export_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 's.sqlite')
            config = monthly.load_config()
            monthly.sync_directory(store)
            args = argparse.Namespace(file=str(FIXTURES / 'dblp_sample.xml'), release='2026-11-01', download=False, force=False)
            monthly.cmd_dblp(args, store, config)
            self.assertFalse(store.lookup(['dblp:journals/access/Foo23']), 'denied venues are never stored')
            fresh = store.works(['prefilter_pass'])
            self.assertEqual([w['title'] for w in fresh], ['A Game-Theoretic Study of Rollup Sequencers'])
            majority = store.lookup(['dblp:conf/ccs/EyalS14'])
            self.assertEqual(store.work(next(iter(majority)))['status'], 'in_directory')
            llm = FakeLLM()
            spend = Spend(store, 'r', 1.0)
            run_stage(store, fresh, stage='title', llm=llm, spend=spend, batch_size=10, log=lambda m: None)
            store.set_abstract(fresh[0]['key'], 'We give a game-theoretic study of rollup sequencers and their fee incentives. ' * 4, 'test')
            run_stage(store, store.works(['title_keep']), stage='abstract', llm=llm, spend=spend, batch_size=10, log=lambda m: None)
            self.assertEqual(store.counts().get('screen_include'), 1)

            class FakeClient:
                def verify(self, seed, observed=()):
                    record = observed[0]
                    return {'status': 'verified', 'conflicts': [], 'versions': [], 'metadata': {
                        **{k: record.get(k) for k in ('title', 'year', 'doi', 'venue', 'kind', 'url')},
                        'authors': [{'name': 'Alice Doe', 'ids': {}}], 'source_ids': {'dblp': record['source_id'], 'arxiv': '2301.00001'}}}

                def lookup_crossref(self, doi):
                    return []
            from promote import promote
            outcome = promote(store, config, apply=False, log=lambda m: None, client=FakeClient())
            self.assertEqual(len(outcome['accepted']), 1)
            self.assertEqual(outcome['accepted'][0]['record']['topic_ids'], ['mining'])
            with patch.object(monthly, 'EXPORT', Path(tmp) / 'ledger.jsonl'):
                monthly.cmd_export(None, store, config)
                store2 = Store(Path(tmp) / 's2.sqlite')
                monthly.cmd_restore(None, store2, config)
                key = next(iter(store2.lookup(['arxiv:2301.00001'])))
                self.assertEqual(store2.screen(key, 'abstract', rubric.version())[0]['decision'], 'include')
                store2.close()
            store.close()


if __name__ == '__main__':
    unittest.main()
