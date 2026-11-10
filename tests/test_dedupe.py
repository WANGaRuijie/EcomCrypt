import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from dedupe import candidates, undecided


TEXT = 'We study strategic miners who deviate from the protocol and measure the resulting revenue across many pools ' * 3


class Duplicates(unittest.TestCase):
    def test_retitled_preprint_is_found_through_its_abstract(self):
        papers = [{'id': 'a', 'title': 'Trade or Trick?', 'authors': ['Ann Lee', 'Bo Chen']},
                  {'id': 'b', 'title': 'Demystifying Scam Tokens on Uniswap', 'authors': ['Ann Lee', 'Bo Chen']}]
        abstracts = {'trade or trick': TEXT, 'demystifying scam tokens on uniswap': TEXT}
        self.assertIn(('a', 'b'), candidates(papers, abstracts))

    def test_similar_title_by_other_authors_is_not_a_candidate(self):
        papers = [{'id': 'a', 'title': 'Transaction Fee Mechanism Design', 'authors': ['Ann Lee']},
                  {'id': 'b', 'title': 'Transaction Fee Mechanism Design', 'authors': ['Tim Roughgarden'], 'doi': None}]
        pairs = candidates(papers, {})
        self.assertEqual([why for why in pairs.values() if 'same authors' in why], [])

    def test_a_reviewed_pair_stops_being_reported(self):
        decisions = {'distinct': [{'ids': ['b', 'a']}]}
        self.assertEqual(undecided({('a', 'b'): 'x', ('a', 'c'): 'y'}, decisions), {('a', 'c'): 'y'})


if __name__ == '__main__':
    unittest.main()
