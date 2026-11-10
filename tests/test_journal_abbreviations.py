import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class JournalAbbreviations(unittest.TestCase):
    def test_every_registered_journal_has_an_iso4_name(self):
        venues = json.loads((ROOT / 'data/venue_registry_v1.json').read_text(encoding='utf-8'))['venues']
        names = json.loads((ROOT / 'data/journal_abbreviations_v1.json').read_text(encoding='utf-8'))['abbreviations']
        journals = {row['id'] for row in venues if row['kind'] == 'journal'}
        self.assertEqual(sorted(journals - set(names)), [])
        self.assertEqual(sorted(set(names) - journals), [])
        self.assertEqual(names['tit'], 'IEEE Trans. Inf. Theory')


if __name__ == '__main__':
    unittest.main()
