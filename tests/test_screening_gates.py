"""Preprint channel policy, excerpt validation and single-source verification."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import metadata
import promote
import rubric
import screen
import venue_policy


class PreprintChannels(unittest.TestCase):
    def decision(self, **record):
        return venue_policy.classify(record)['decision']

    def test_accepted_channels(self):
        for venue in ('arXiv (Cornell University)', 'CoRR', 'IACR Cryptol. ePrint Arch.', 'SSRN Electronic Journal',
                      'RePEc: Research Papers in Economics', 'Munich Personal RePEc Archive (Ludwig Maximilian University of Munich)',
                      'NBER Working Papers', 'Optimization Online'):
            self.assertEqual(self.decision(venue=venue, kind='preprint'), 'preprint', venue)

    def test_other_repositories_are_denied(self):
        for venue in ('Zenodo (CERN European Organization for Nuclear Research)', 'Research Square', 'HAL',
                      'DSpace@MIT (Massachusetts Institute of Technology)', 'Electron. Colloquium Comput. Complex.'):
            self.assertEqual(self.decision(venue=venue, kind='preprint'), 'deny', venue)
        self.assertEqual(self.decision(venue='Zenodo (CERN European Organization for Nuclear Research)'), 'deny')
        self.assertEqual(self.decision(doi='10.5281/zenodo.1', venue='Some Title'), 'deny')

    def test_formal_venues_survive_a_preprint_label(self):
        self.assertEqual(self.decision(venue='TARK', kind='preprint'), 'preprint')
        self.assertEqual(self.decision(venue='DROPS (Schloss Dagstuhl)', kind='preprint', doi='10.4230/lipics.aft.2026.1'), 'preprint')

    def test_archive_identity_beats_a_missing_venue(self):
        self.assertEqual(self.decision(kind='preprint', source='arxiv'), 'preprint')
        self.assertEqual(self.decision(kind='preprint', doi='10.2139/ssrn.123'), 'preprint')
        self.assertEqual(self.decision(kind='preprint', source='openalex'), 'unresolved')


class VenueLanguage(unittest.TestCase):
    def test_non_english_names_are_denied(self):
        for venue in ('计算机科学', 'Хозяйство и право', 'Revue économique', 'Jurnal Halal Center', 'Bilişim Teknolojileri Dergisi',
                      'Datenschutz und Datensicherheit', 'Jahrbücher für Nationalökonomie und Statistik'):
            verdict = venue_policy.classify({'venue': venue})
            self.assertEqual((verdict['decision'], verdict.get('rule')), ('deny', 'non-english-venue'), venue)

    def test_english_and_registered_names_pass(self):
        self.assertNotEqual(venue_policy.classify({'venue': 'IEEE Trans. Circuits Syst. I Regul. Pap.'})['decision'], 'deny')
        self.assertEqual(venue_policy.classify({'venue': 'Canadian Journal of Economics/Revue canadienne d économique'})['decision'], 'allow')
        self.assertEqual(venue_policy.classify({'venue': 'Information & Management'})['decision'], 'allow')

    def test_gamesec_is_econcs(self):
        self.assertEqual(venue_policy.classify({'venue': 'GameSec'})['group'], 'EconCS')


SOURCE = ('We study effective-balance rules as a mechanism-design problem, and we propose capacity-adjusted illiquidity, '
          'a survival statistic that scales price impact by the square root of the market’s absorption capacity.')


class ExcerptValidation(unittest.TestCase):
    def test_copying_noise_is_tolerated(self):
        self.assertTrue(rubric.excerpt_supported('effective balance rules as a mechanism design problem', SOURCE))
        self.assertTrue(rubric.excerpt_supported("the market's absorption capacity", SOURCE))
        self.assertTrue(rubric.excerpt_supported(
            'we propose capacity-adjusted illiquidity, a survival statistic that scales impact by the square root of the market’s absorption capacity', SOURCE))

    def test_invented_text_fails(self):
        self.assertFalse(rubric.excerpt_supported('we design a truthful auction for validators with budget constraints', SOURCE))
        self.assertFalse(rubric.excerpt_supported('', SOURCE))
        self.assertFalse(rubric.excerpt_supported('...', SOURCE))

    def test_shuffled_words_fail(self):
        self.assertFalse(rubric.excerpt_supported('capacity absorption market square root impact price scales statistic survival', SOURCE))

    def test_row_with_noisy_excerpts_stays_included(self):
        row = {'decision': 'include', 'topics': [next(iter(rubric.topics()))], 'confidence': 'high',
               'evidence_T': 'effective balance rules', 'evidence_E': 'mechanism design problem'}
        self.assertEqual(rubric.validate_abstract_row(row, {'id': 'p0', 'title': 'T', 'abstract': SOURCE})['decision'], 'include')


class FakeClient:
    def __init__(self, status='partial', source_ids=None):
        self.status, self.source_ids = status, source_ids or {'openalex': 'W1'}
        self.observed, self.dois = None, []

    def lookup_crossref(self, doi):
        self.dois.append(doi)
        return [{'source': 'crossref', 'title': 'T'}]

    def verify(self, seed, observed=()):
        self.observed = list(observed)
        return {'status': self.status, 'metadata': {'source_ids': self.source_ids}, 'conflicts': [], 'evidence': [], 'versions': []}


OPENALEX = {'title': 'T', 'authors': [{'name': 'A B'}], 'year': 2026, 'venue': 'ICBC', 'kind': 'conference-paper',
            'doi': '10.1109/icbc.1', 'source': 'openalex', 'source_id': 'W1'}


class Verification(unittest.TestCase):
    def test_all_local_editions_are_evidence(self):
        client = FakeClient('verified')
        dblp = {'title': 'T', 'source': 'dblp', 'source_id': 'conf/x/1'}
        other = {'title': 'T', 'source': 'unknown', 'source_id': 'x'}
        promote.verify(client, OPENALEX, [OPENALEX, dblp, other])
        sources = [r['source'] for r in client.observed]
        self.assertEqual(sources.count('openalex'), 1)
        self.assertIn('dblp', sources)
        self.assertNotIn('unknown', sources)

    def test_doi_is_looked_up_in_crossref(self):
        client = FakeClient('verified')
        promote.verify(client, OPENALEX, [OPENALEX])
        self.assertEqual(client.dois, ['10.1109/icbc.1'])

    def test_arxiv_doi_uses_the_archive_route(self):
        client = FakeClient()
        record = {**OPENALEX, 'venue': 'arXiv (Cornell University)', 'kind': 'preprint', 'doi': '10.48550/arxiv.2601.1'}
        result = promote.verify(client, record, [record])
        self.assertEqual(client.dois, [])
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['verification_basis'], 'primary_archive_metadata_not_peer_review')

    def test_ssrn_without_second_source_stays_partial(self):
        record = {**OPENALEX, 'venue': 'SSRN Electronic Journal', 'kind': 'preprint', 'doi': '10.2139/ssrn.1'}
        self.assertEqual(promote.verify(FakeClient(), record, [record])['status'], 'partial')


class Prefilter(unittest.TestCase):
    def passes(self, title, group=None):
        return rubric.prefilter(title, '', group)[0]

    def test_ambiguous_chain_words_keep_real_papers(self):
        for title in ("The Miner's Dilemma", 'FruitChains', 'Decentralization through Tokenization', 'Order-Fairness for Byzantine Consensus'):
            self.assertTrue(self.passes(title), title)

    def test_other_fields_are_dropped(self):
        for title in ('Conv-CoA: Improving Open-domain Question Answering via Conversational Chain-of-Action',
                      'Speed-up of Vision Transformer Models by Attention-aware Token Filtering', 'Visual Concepts Tokenization'):
            self.assertFalse(self.passes(title), title)

    def test_preprints_need_a_specific_economic_term(self):
        self.assertTrue(self.passes('A Small Collusion is All You Need', 'Preprint'))
        self.assertFalse(self.passes('Algorithm Instance Games', 'Preprint'))

    def test_security_games_pass_without_a_venue_group(self):
        for title in ('Layered Graph Security Games', 'Stackelberg Network Interdiction Games'):
            self.assertTrue(self.passes(title), title)


class Retry(unittest.TestCase):
    def test_only_excerpt_failures_are_retried(self):
        class Store:
            def __init__(self, result):
                self.result = result

            def screen(self, *_):
                return self.result, screen._hash({'title': 'T', 'venue': '', 'year': None, 'abstract': ''})

        work = {'key': 'k', 'title': 'T'}
        flagged = {'decision': 'needs_fulltext', 'validation': 'evidence_E_not_verbatim,include_without_both_excerpts'}
        self.assertTrue(screen.needs_screen(Store(flagged), work, 'abstract', 'v', True)[0])
        self.assertFalse(screen.needs_screen(Store(flagged), work, 'abstract', 'v')[0])
        self.assertFalse(screen.needs_screen(Store({'decision': 'needs_fulltext'}), work, 'abstract', 'v', True)[0])


class VenueMatching(unittest.TestCase):
    def verdict(self, venue):
        result = venue_policy.classify({'venue': venue})
        return result['decision'], result.get('venue_id')

    def test_dblp_volume_suffixes(self):
        self.assertEqual(self.verdict('CRYPTO (2)'), ('allow', 'crypto'))
        self.assertEqual(self.verdict('TCC (B1)'), ('allow', 'tcc'))
        self.assertEqual(self.verdict('FC (Workshops 1)'), ('allow', 'fc-workshops'))

    def test_a_registered_name_inside_another_title_does_not_match(self):
        for venue in ('Studies in Economics and Finance', 'Chinese Control Conference (CCC)', 'Quantum Information and Computation',
                      'Annals of Mathematics and Artificial Intelligence'):
            self.assertEqual(self.verdict(venue)[0], 'unknown', venue)

    def test_proceedings_wording_still_matches(self):
        self.assertEqual(self.verdict('Proceedings of the thirty-sixth annual ACM symposium on Theory of computing'), ('allow', 'stoc'))
        self.assertEqual(self.verdict('2013 IEEE 54th Annual Symposium on Foundations of Computer Science'), ('allow', 'focs'))

    def test_side_tracks_are_not_the_main_venue(self):
        self.assertEqual(self.verdict('WWW (Companion Volume)'), ('allow', 'www-companion'))
        self.assertEqual(self.verdict('GLOBECOM (Workshops)')[0], 'unknown')

    def test_display_rows_drop_volume_noise(self):
        self.assertEqual(venue_policy.venue_row('CRYPTO (8)')['label'], 'CRYPTO')
        self.assertEqual(venue_policy.venue_row('SIGMETRICS (Abstracts)')['label'], 'SIGMETRICS')
        self.assertIsNone(venue_policy.venue_row('Chinese Control Conference (CCC)'))

    def test_ice_economies_is_not_the_concurrency_workshop(self):
        self.assertEqual(self.verdict('International Conference on Information and Computation Economies (ICE)'), ('allow', 'ice-economies'))
        self.assertEqual(self.verdict('ICE')[0], 'unknown')


class NearDuplicates(unittest.TestCase):
    def edition(self, title, authors, preprint=True, year=2024):
        return promote._edition_print(title, authors, year, preprint, title)

    def test_retitled_preprint_is_the_same_work(self):
        self.assertTrue(promote._same_work(self.edition('BRC-20: Hope or Hype', ['Qin Wang', 'Guangsheng Yu']),
                                           self.edition('Understanding BRC-20: Hope or Hype', ['Qin Wang', 'Guangsheng Yu'], False)))

    def test_two_formal_papers_coexist(self):
        self.assertFalse(promote._same_work(self.edition('Musketeer Protocols', ['A B', 'C D'], False), self.edition('Musketeer Protocols', ['A B', 'C D'], False)))

    def test_other_authors_are_another_work(self):
        self.assertFalse(promote._same_work(self.edition('Optimal Fee Markets for Rollups', ['A Smith', 'B Jones']),
                                            self.edition('Optimal Fee Markets for Rollups', ['C Lee', 'D Kim'], False)))


class Batches(unittest.TestCase):
    def item(self, title, kind, venue, confidence='high'):
        return {'title': title, 'screen': {'confidence': confidence}, 'record': {'verification': {'metadata': {'venue': venue, 'kind': kind}}}}

    def test_filters(self):
        formal = self.item('Fee Markets', 'proceedings-article', 'EC')
        preprint = self.item('Fee Markets', 'preprint', 'CoRR', 'medium')
        self.assertTrue(promote.in_batch(formal, {'confidence': 'high', 'kind': 'formal'}))
        self.assertFalse(promote.in_batch(preprint, {'kind': 'formal'}))
        self.assertFalse(promote.in_batch(preprint, {'confidence': 'high'}))
        self.assertTrue(promote.in_batch(formal, {'groups': {'EconCS'}}))
        self.assertFalse(promote.in_batch(formal, {'groups': {'TCS'}}))

    def test_preprint_soks_wait_for_a_human(self):
        self.assertFalse(promote.in_batch(self.item('SoK: Cross-Domain MEV', 'preprint', 'CoRR'), {}))
        self.assertTrue(promote.in_batch(self.item('SoK: Cross-Domain MEV', 'proceedings-article', 'CCS'), {}))


class AuthorNames(unittest.TestCase):
    def same(self, left, right):
        return metadata._same_person({'name': left, 'ids': {}}, {'name': right, 'ids': {}})

    def test_spelling_variants(self):
        for left, right in (('Burcu Yıldız', 'Burcu Yildiz'), ('Han, Chunghyun', 'Chunghyun Han'), ('Lu Yun', 'Yun Lu'),
                            ('Sheng-Nan Li', 'Shengnan Li'), ('Claudio Juan Tessone', 'Claudio J. Tessone'), ('Brett Hemenway', 'Brett Hemenway Falk')):
            self.assertTrue(self.same(left, right), left)

    def test_different_people(self):
        self.assertFalse(self.same('Ana Torres', 'Lara Torres'))
        self.assertFalse(self.same('Ana Torres', 'Ana Lopez'))

    def test_a_wrong_orcid_does_not_split_one_name(self):
        self.assertTrue(metadata._same_person({'name': 'Tao Li', 'ids': {'orcid': '1'}}, {'name': 'Tao Li', 'ids': {'orcid': '2'}}))


if __name__ == '__main__':
    unittest.main()
