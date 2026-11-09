import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from discovery_ranking import review_priority


class RankingTests(unittest.TestCase):
    def candidate(self, title, author='A1', abstract=''):
        return {'record': {'title': title, 'source_id': title, 'venue': 'arXiv',
                           'kind': 'preprint', 'authors': [{'ids': {'openalex': author}}],
                           'abstract': abstract}, 'hints': [], 'seeds': []}

    def test_intersection_without_abstract_precedes_famous_unrelated_work(self):
        unrelated = self.candidate('A circuit complexity theorem', 'priority')
        relevant = self.candidate('Transaction fee mechanisms against collusion')
        self.assertLess(review_priority(relevant, {'priority'}),
                        review_priority(unrelated, {'priority'}))
        with_abstract = self.candidate(relevant['record']['title'], abstract='Full abstract')
        self.assertEqual(review_priority(relevant, set()), review_priority(with_abstract, set()))

    def test_requested_identity_breaks_ties_between_relevant_candidates(self):
        other = self.candidate('Bitcoin fee mechanism', 'other')
        requested = self.candidate('Bitcoin fee mechanism', 'priority')
        self.assertLess(review_priority(requested, {'priority'}),
                        review_priority(other, {'priority'}))
