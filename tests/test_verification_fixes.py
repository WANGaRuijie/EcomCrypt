import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from metadata import _title_match, reconcile


def record(source, source_id, title, year, venue, doi=None, kind='journal-article', authors=('Ann Lee', 'Bo Chen')):
    return {'source': source, 'source_id': source_id, 'title': title, 'year': year, 'venue': venue, 'doi': doi, 'kind': kind,
            'authors': [{'name': name, 'ids': {}, 'institutions': []} for name in authors], 'related_dois': []}


class VerificationFixes(unittest.TestCase):
    def test_hyphenation_does_not_split_a_title(self):
        seed = {'title': 'Is Bitcoin Really Un-Tethered?', 'authors': ['Ann Lee']}
        self.assertEqual(_title_match(seed, {'title': 'Is Bitcoin Really Untethered?'}), 'exact_title')

    def test_the_seed_doi_matches_a_retitled_journal_version(self):
        seed = {'title': 'Bitcoin As Decentralized Money', 'doi': '10.1093/rfs/hhaa149', 'authors': ['Ann Lee', 'Bo Chen']}
        journal = record('crossref', '10.1093/rfs/hhaa149', 'Decentralizing Money: Bitcoin Prices and Blockchain Security', 2022, 'Rev. Financ. Stud.', '10.1093/rfs/hhaa149')
        self.assertEqual(_title_match(seed, journal), 'same_doi')
        self.assertIsNone(_title_match({**seed, 'authors': ['Someone Else']}, journal))

    def test_dblp_alone_verifies_a_formal_paper_but_not_a_preprint(self):
        seed = {'title': 'Speculative Denial-of-Service Attacks in Ethereum', 'year': 2024, 'authors': ['Ann Lee', 'Bo Chen']}
        formal = record('dblp', 'conf/uss/X24', seed['title'], 2024, 'USENIX Security Symposium', kind='proceedings-article')
        self.assertEqual(reconcile(seed, [formal])['status'], 'verified')
        preprint = record('dblp', 'journals/corr/X24', seed['title'], 2024, 'CoRR', kind='preprint')
        self.assertNotEqual(reconcile(seed, [preprint])['status'], 'verified')


if __name__ == '__main__':
    unittest.main()
