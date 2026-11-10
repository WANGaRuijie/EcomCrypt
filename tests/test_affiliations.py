import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from affiliations_llm import _decide, _export, name_key


PERSON = {'bylines': {'Old University': 2015, 'Carnegie Mellon University': 2022}}


class Affiliations(unittest.TestCase):
    def test_name_key_matches_the_site(self):
        self.assertEqual(name_key('Tomáš  Brázdil 2024'), 'tomas brazdil')

    def test_a_sure_move_overrides_the_bylines(self):
        self.assertEqual(_decide(PERSON, {'affiliation': 'UC Berkeley', 'basis': 'knowledge', 'confidence': 'high'}), ('UC Berkeley', 'knowledge'))

    def test_an_unsure_move_falls_back_to_the_newest_byline(self):
        self.assertEqual(_decide(PERSON, {'affiliation': 'UC Berkeley', 'basis': 'knowledge', 'confidence': 'medium'}), ('Carnegie Mellon University', 'byline'))

    def test_no_evidence_and_no_certainty_stays_unknown(self):
        self.assertEqual(_decide({'bylines': {}}, {'affiliation': 'Somewhere', 'basis': 'byline'}), (None, 'none'))

    def test_export_folds_variants_and_applies_manual_entries(self):
        document = {'records': {'a': {'affiliation': 'Cornell Tech'}, 'b': {'affiliation': None}}, 'variants': {}, 'manual_variants': {'Cornell Tech': 'Cornell University'}, 'manual_affiliations': {'c': 'X'}}
        self.assertEqual(_export(document), {'a': 'Cornell University', 'c': 'X'})


if __name__ == '__main__':
    unittest.main()
