import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from springer_proceedings import scan_book

class SpringerCoverageTests(unittest.TestCase):
    def test_pagination_and_no_inferred_metadata_or_adoption(self):
        book={'url':'https://link.springer.com/book/10.1007/example','venue':'CBT','event_year':2025,'part':'I','track':'workshop'}
        page=lambda suffix,title:f'<h2>Table of contents (2 papers)</h2><li data-test="chapter"><a href="/chapter/10.1007/example_{suffix}">{title}</a>Pages 1-20</li>'
        first=page('1','A &amp; B')+'<a href="?page=2#toc" rel="next">Next</a>'
        rows,status=scan_book(book,lambda url:first if '?' not in url else page('2','Second'))
        self.assertTrue(status['complete']);self.assertEqual(len(status['pages_checked']),2)
        self.assertEqual(rows[0]['title'],'A & B');self.assertIsNone(rows[0]['year'])
        self.assertEqual(rows[0]['authors'],[]);self.assertEqual(rows[0]['venue'],'CBT')
        self.assertEqual(status['contribution_reviews'],0);self.assertEqual(status['adopted'],0)
        _,limited=scan_book(book,lambda _:first,max_pages=1)
        self.assertFalse(limited['complete']);self.assertIn('page=2',limited['next_cursor'])

    def test_challenge_or_missing_chapters_cannot_be_complete(self):
        book={'url':'https://link.springer.com/book/10.1007/example','venue':'ESORICS','event_year':2025,'part':'I','track':'main'}
        _,status=scan_book(book,lambda _:'<html>Access denied</html>')
        self.assertEqual(status['status'],'unavailable');self.assertFalse(status['complete'])
        _,status=scan_book(book,lambda _:'Table of contents (25 papers)')
        self.assertEqual(status['status'],'incomplete');self.assertFalse(status['complete'])
