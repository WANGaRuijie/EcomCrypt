from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from venue_sources import resolve_sources


class VenueResolutionTests(unittest.TestCase):
    def test_conference_and_journal_search_results_cannot_be_confused(self):
        client = Mock(refresh=False, offline=False, openalex_key="test-key")
        client.cache_dir = Path(__file__).resolve().parents[1] / ".out" / "test-venue-resolution"
        client._download.return_value = {"results": [
            {"id": "https://openalex.org/S1", "display_name": "ACM Conference on Economics and Computation", "type": "conference"},
            {"id": "https://openalex.org/S2", "display_name": "ACM Transactions on Economics and Computation", "type": "journal"},
        ]}
        venue = {"id": "teac", "name": "ACM Transactions on Economics and Computation", "aliases": [], "kind": "journal"}
        with patch("venue_sources.cache_path") as cache, patch("venue_sources.write_json") as write:
            cache.return_value.exists.return_value = False
            result = resolve_sources(client, venue)
        self.assertEqual(result["matches"][0]["id"], "https://openalex.org/S2")
        self.assertNotIn("test-key", result["query_url"])
        self.assertNotIn("test-key", str(write.call_args))

    def test_duplicate_named_sources_remain_unresolved(self):
        client = Mock(refresh=False, offline=False, openalex_key=None)
        client.cache_dir = Path(".out")
        client._download.return_value = {"results": [
            {"id": "https://openalex.org/S1", "display_name": "Games and Economic Behavior", "type": "journal"},
            {"id": "https://openalex.org/S2", "display_name": "Games and Economic Behavior", "type": "journal"},
        ]}
        venue = {"id": "geb", "name": "Games and Economic Behavior", "aliases": [], "kind": "journal"}
        with patch("venue_sources.cache_path") as cache, patch("venue_sources.write_json"):
            cache.return_value.exists.return_value = False
            result = resolve_sources(client, venue)
        self.assertEqual(result["status"], "unresolved")
