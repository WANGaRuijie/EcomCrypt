import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

from scripts.metadata import (
    MetadataClient,
    MetadataError,
    cache_path,
    normalize_doi,
    normalize_title,
    public_query_url,
    reconcile,
    seed_queries,
    _crossref_record,
)


TITLE = "Cryptographic Incentives: An Example"


class VenueContainerTests(unittest.TestCase):
    def test_429_backoff_survives_a_new_client_but_does_not_block_cached_evidence(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            with patch('scripts.metadata.time.time',return_value=1000),patch('scripts.metadata.urlopen',
                side_effect=HTTPError('https://api.openalex.org',429,'rate limited',{'Retry-After':'7200'},None)) as fetch:
                with self.assertRaisesRegex(MetadataError,'http_429$'):
                    MetadataClient(folder)._fetch('openalex',{'search':'first'})
                with self.assertRaisesRegex(MetadataError,'source_backoff'):
                    MetadataClient(folder)._fetch('openalex',{'search':'different'})
                self.assertEqual(fetch.call_count,1)
                url=public_query_url('openalex',{'search':'cached'})
                cache_path(folder,url).write_text(json.dumps({'url':url,'payload':{'results':[]}}),encoding='utf-8')
                self.assertEqual(MetadataClient(folder)._fetch('openalex',{'search':'cached'})['payload'],{'results':[]})
                cooldown=json.loads((Path(folder)/'source-backoff/openalex.json').read_text())
                self.assertEqual(cooldown['retry_after_epoch'],8200)
    def test_dblp_non_json_backoff_survives_a_new_client_and_expires(self):
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            response = MagicMock()
            response.__enter__.return_value.read.return_value = b'<html>challenge</html>'
            with patch('scripts.metadata.urlopen', return_value=response) as fetch, patch('scripts.metadata.time.time', return_value=1000):
                with self.assertRaisesRegex(MetadataError, 'invalid_json$'):
                    MetadataClient(folder)._fetch('dblp', {'q': 'first', 'h': 8, 'format': 'json'})
                with self.assertRaisesRegex(MetadataError, 'source_backoff'):
                    MetadataClient(folder)._fetch('dblp', {'q': 'different', 'h': 8, 'format': 'json'})
                self.assertEqual(fetch.call_count, 1)
            with patch('scripts.metadata.time.time', return_value=4601), patch('scripts.metadata.urlopen', return_value=response) as fetch:
                with self.assertRaisesRegex(MetadataError, 'invalid_json$'):
                    MetadataClient(folder)._fetch('dblp', {'q': 'different', 'h': 8, 'format': 'json'})
                self.assertEqual(fetch.call_count, 1)

    def test_rate_limited_provider_stops_new_requests_for_this_client(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            client=MetadataClient(folder)
            with patch('scripts.metadata.urlopen', side_effect=HTTPError('https://dblp.org',429,'rate limited',{},None)) as fetch:
                with self.assertRaisesRegex(MetadataError,'http_429'):
                    client._download('dblp',Request('https://dblp.org/search/publ/api'))
                with self.assertRaisesRegex(MetadataError,'session_backoff'):
                    client._download('dblp',Request('https://dblp.org/search/publ/api'))
                self.assertEqual(fetch.call_count,1)

    def test_crossref_book_title_takes_precedence_over_series(self):
        record = _crossref_record({"type": "book-chapter", "DOI": "10.1234/example",
            "container-title": ["Lecture Notes in Computer Science", "Financial Cryptography and Data Security"]})
        self.assertEqual(record["venue"], "Financial Cryptography and Data Security")
SEED = {"title": TITLE, "authors": ["Torres"], "year": 2024, "venue": "EC"}


def author(name="Ana Torres", **ids):
    return {"name": name, "ids": ids, "institutions": []}


def record(source="openalex", **overrides):
    return {
        "source": source,
        "source_id": {"openalex": "W1", "crossref": "10.1234/example", "dblp": "conf/ec/T24"}[source],
        "title": TITLE,
        "year": 2024,
        "doi": "10.1234/example",
        "venue": "ACM Conference on Economics and Computation (EC)",
        "kind": "proceedings-article",
        "authors": [author()],
        "url": "https://doi.org/10.1234/example",
        "related_dois": [],
        **overrides,
    }


class ReconciliationTests(unittest.TestCase):
    def test_missing_authority_does_not_promote_seed_hints(self):
        self.assertEqual(reconcile(SEED, [])["status"], "unverified")
        self.assertIsNone(reconcile(SEED, [])["metadata"])
        sparse = record(doi=None, year=None, authors=[])
        result = reconcile(SEED, [sparse])
        self.assertEqual(result["status"], "partial")
        self.assertIsNone(result["metadata"]["doi"])
        self.assertIsNone(result["metadata"]["year"])
        self.assertEqual(result["metadata"]["authors"], [])

    def test_shared_doi_corrobates_and_retains_affiliation_source(self):
        affiliation = {"name": "Example University", "ids": {"ror": "02bxkxs79"}}
        openalex = record(authors=[{**author("Ana B. Torres", openalex="A1"), "institutions": [affiliation]}])
        dblp = record("dblp", authors=[author("Ana Torres", dblp="12/3456")])
        result = reconcile(SEED, [openalex, dblp])
        self.assertEqual(result["status"], "verified")
        person = result["metadata"]["authors"][0]
        self.assertEqual(person["ids"], {"dblp": "12/3456", "openalex": "A1"})
        self.assertEqual(
            person["institutions"],
            [{**affiliation, "source": "openalex", "source_id": "W1", "year": 2024}],
        )

    def test_distant_repost_does_not_replace_original_edition(self):
        repost = record(doi="10.2139/ssrn.123", year=2020, kind="journal-article", venue="SSRN")
        result = reconcile(SEED, [repost])
        self.assertEqual(result["status"], "unverified")
        self.assertIsNone(result["metadata"])
        self.assertEqual(result["evidence"][0]["doi"], "10.2139/ssrn.123")

    def test_short_title_venue_and_year_distinguish_published_version(self):
        preprint = record(
            doi="10.48550/arxiv.123", year=2023, venue="arXiv", kind="preprint",
        )
        proceedings = record("crossref", title="Cryptographic Incentives")
        result = reconcile(SEED, [preprint, proceedings])
        self.assertEqual(result["metadata"]["doi"], proceedings["doi"])
        self.assertEqual([version["doi"] for version in result["versions"]], [preprint["doi"]])
        wrong_year = {**proceedings, "year": 2025}
        self.assertEqual(reconcile(SEED, [wrong_year])["status"], "unverified")

    def test_two_dois_cannot_be_bridged_by_unidentified_mirror(self):
        competing = record("crossref", doi="10.5678/other")
        mirror = record("dblp", doi=None, venue=None)
        result = reconcile(SEED, [record(), competing, mirror])
        self.assertEqual(result["status"], "ambiguous")
        self.assertIsNone(result["metadata"])

    def test_seed_year_selects_cited_edition_without_merging_dois(self):
        later = record("crossref", year=2026, doi="10.1234/later", kind="journal-article")
        result = reconcile(SEED, [record(), later])
        self.assertEqual(result["metadata"]["doi"], record()["doi"])
        self.assertEqual(result["versions"], [])
        self.assertIn(later["doi"], [evidence["doi"] for evidence in result["evidence"]])

    def test_edition_year_conflict_prefers_explicit_print_date(self):
        early = record(year=2023)
        publisher = record("crossref", year_fields={"published-print": 2024})
        result = reconcile(SEED, [early, publisher])
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["metadata"]["year"], 2024)
        self.assertEqual(result["conflicts"], [])

    def test_distant_years_from_registrars_stay_a_conflict(self):
        result = reconcile(SEED, [record("dblp", year=2021), record("crossref", year=2024)])
        self.assertEqual(result["status"], "partial")
        self.assertIn("source_disagreement", [item["reason"] for item in result["conflicts"]])

    def test_openalex_preprint_year_yields_to_registrars(self):
        result = reconcile({**SEED, "year": 2024}, [record(year=2020), record("crossref", year=2024), record("dblp", year=2024)])
        self.assertEqual((result["status"], result["metadata"]["year"]), ("verified", 2024))

    def test_conflicting_author_is_not_linked_to_publisher_byline(self):
        result = reconcile(SEED, [
            record(authors=[author("Lara Torres", openalex="A123")]),
            record("crossref"),
        ])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["metadata"]["authors"], [author()])


class MetadataClientTests(unittest.TestCase):
    def test_title_entities_do_not_create_false_bibliographic_conflicts(self):
        self.assertEqual(normalize_title('Governance &amp; Social Contract Theories'),
                         normalize_title('Governance & Social Contract Theories'))
        self.assertEqual(normalize_title('M&#225;i&#8217;s Mining'), normalize_title('Mái’s Mining'))
        self.assertNotEqual(normalize_title('Mining incentives'), normalize_title('Mining incentives revised'))

    def test_normalization(self):
        self.assertEqual(normalize_title("Mái’s Mining — DéFi"), "mais mining defi")
        self.assertEqual(normalize_doi("HTTPS://doi.org/10.1234/Ab%2FC"), "10.1234/ab/c")
        self.assertIsNone(normalize_doi("https://example.org/10.1234/abc"))

    def test_offline_replay_and_exact_crossref_lookup(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temporary:
            queries = seed_queries(TITLE)
            responses = {
                "openalex": {
                    "results": [{
                        "id": "https://openalex.org/W1", "doi": "https://doi.org/10.1234/example",
                        "title": TITLE, "publication_year": 2024,
                        "authorships": [{"author": {"id": "https://openalex.org/A1", "display_name": "Ana Torres"}}],
                        "primary_location": {"source": {"display_name": "EC"}},
                    }],
                },
                "dblp": {"result": {"hits": {"@total": "0"}}},
                "crossref": {"message": {"items": []}},
            }

            def cache(source, params, payload):
                url = public_query_url(source, params)
                cache_path(temporary, url).write_text(
                    json.dumps({"url": url, "retrieved_at": "2026-11-06", "payload": payload}),
                    encoding="utf-8",
                )

            for source, payload in responses.items():
                cache(source, queries[source], payload)
            cache("crossref", {"doi": "10.1234/example"}, {"message": {
                "DOI": "10.1234/example", "title": [TITLE], "container-title": ["EC"],
                "author": [{"given": "Ana", "family": "Torres"}],
                "published-print": {"date-parts": [[2024, 7]]},
                "type": "proceedings-article",
            }})
            client = MetadataClient(temporary, offline=True, openalex_key="unexposed-secret")
            result = client.verify(SEED)
            self.assertEqual(result["status"], "verified")
            self.assertEqual(len(result["queries"]), 4)
            self.assertNotIn("unexposed-secret", json.dumps(result))
            self.assertTrue(all(row["retrieved_at"] == "2026-11-06" for row in result["evidence"]))
            with self.assertRaisesRegex(MetadataError, "offline_cache_miss"):
                client.search_openalex({"search": "uncached"})


if __name__ == "__main__":
    unittest.main()
