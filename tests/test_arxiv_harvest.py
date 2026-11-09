import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from arxiv_harvest import parse_feed

class ArxivTests(unittest.TestCase):
    def test_primary_archive_metadata_retains_publication_link_without_inventing_preprint_doi(self):
        raw='''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
        <entry><id>http://arxiv.org/abs/2401.12345v3</id><title>Game Theoretic Security</title>
        <published>2024-01-02T00:00:00Z</published><summary>Strategic security.</summary>
        <author><name>Alice Example</name></author><category term="cs.GT"/>
        <arxiv:doi>10.1234/published</arxiv:doi><arxiv:journal_ref>EC 2025</arxiv:journal_ref></entry></feed>'''
        record=parse_feed(raw.encode())[0]
        self.assertEqual(record['source_id'],'2401.12345')
        self.assertIsNone(record['doi'])
        self.assertEqual(record['published_doi'],'10.1234/published')
        self.assertEqual(record['authors'][0]['name'],'Alice Example')
        self.assertEqual(record['year'],2024)
        self.assertEqual(record['categories'],['cs.GT'])
        self.assertFalse(record['is_retracted'])
