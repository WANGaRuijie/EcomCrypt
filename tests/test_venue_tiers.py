import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from monthly import in_queue_order
from venue_policy import is_top, queue_rank


class VenueTiers(unittest.TestCase):
    def test_every_tier_label_is_registered(self):
        labels = {row['label'] for row in json.loads((ROOT / 'data/venue_registry_v1.json').read_text(encoding='utf-8'))['venues']}
        tiers = json.loads((ROOT / 'data/venue_tiers_v1.json').read_text(encoding='utf-8'))
        named = [label for group in tiers['top'].values() for label in group] + tiers['low'] + tiers['deferred']
        self.assertEqual([label for label in named if label not in labels], [])

    def test_owner_anchors_set_the_floor(self):
        self.assertTrue(is_top('AFT'))
        self.assertTrue(is_top('FC'))
        self.assertFalse(is_top('GameSec'))
        self.assertFalse(is_top('FC Workshops'))

    def test_queue_puts_better_venues_first_and_defers_ssrn(self):
        works = [{'venue': name} for name in ('SSRN Electronic Journal', 'BCCA', 'arXiv', 'GameSec', 'Financial Cryptography and Data Security')]
        self.assertEqual([queue_rank(work['venue']) for work in works], [9, 3, 2, 1, 0])
        ordered = [work['venue'] for work in in_queue_order(works)]
        self.assertEqual(ordered, ['Financial Cryptography and Data Security', 'GameSec', 'arXiv', 'BCCA'])
        self.assertEqual(len(in_queue_order(works, include_deferred=True)), 5)

    def test_micro_theory_goes_ahead_of_other_top_venues(self):
        tiers = json.loads((ROOT / 'data/venue_tiers_v1.json').read_text(encoding='utf-8'))
        labels = {row['label'] for row in json.loads((ROOT / 'data/venue_registry_v1.json').read_text(encoding='utf-8'))['venues']}
        self.assertEqual([label for label in tiers['first'] if label not in labels], [])
        self.assertEqual(queue_rank('Games and Economic Behavior'), -1)
        self.assertEqual(queue_rank('The Journal of Finance'), 0)
        ordered = in_queue_order([{'venue': 'The Journal of Finance'}, {'venue': 'Games and Economic Behavior'}])
        self.assertEqual(ordered[0]['venue'], 'Games and Economic Behavior')


if __name__ == '__main__':
    unittest.main()
