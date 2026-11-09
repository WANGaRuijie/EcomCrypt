from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from harvest import CandidateGraph, collect, collect_citations, hydrate_dblp, seed_anchors
from metadata import MetadataError


class HarvestTests(unittest.TestCase):
    def test_citation_resume_continues_cursor_without_restarting_first_page(self):
        graph = CandidateGraph({'papers': []}); client = Mock()
        client._fetch.return_value = {'url': 'https://api.openalex.org/works', 'payload': {'results': [], 'meta': {'next_cursor': None}}}
        state = {'discovery_lane_progress': {'citations:gs-1:W1': {'window': 'same', 'complete': False, 'next_cursor': 'next-page'}}}
        collect_citations(client, graph, 'gs-1', 'W1', 'same', 1, state)
        self.assertEqual(client._fetch.call_args.args[1]['cursor'], 'next-page')
        self.assertEqual(graph.coverage[-1]['window'], 'same')

    def test_terminal_citation_cursor_is_reused_only_for_same_window(self):
        state = {'discovery_lane_progress': {'citations:gs-1:W1': {'window': 'old', 'complete': True, 'next_cursor': None}}}
        graph = CandidateGraph({'papers': []}); client = Mock()
        collect_citations(client, graph, 'gs-1', 'W1', 'old', 1, state)
        client._fetch.assert_not_called()
        self.assertEqual(graph.coverage[-1]['status'], 'already_complete')
        client._fetch.return_value = {'url': 'https://api.openalex.org/works', 'payload': {'results': [], 'meta': {'next_cursor': None}}}
        collect_citations(client, graph, 'gs-1', 'W1', 'new', 1, state)
        self.assertEqual(client._fetch.call_args.args[1]['cursor'], '*')

    def test_primary_verified_work_without_index_ids_keeps_doi_dedup(self):
        work = {'id': 'primary-work', 'title': 'Fee markets', 'topic_ids': ['tfm'],
                'doi': '10.1234/formal', 'source_ids': None,
                'versions': [{'doi': None, 'source_ids': None}],
                'publications': [{'source_ids': None}]}
        graph = CandidateGraph({'papers': [work]})
        graph.add({'source': 'publisher', 'source_id': 'formal', 'title': 'Fee markets',
                   'doi': '10.1234/formal'}, 'proceedings')
        self.assertTrue(next(iter(graph.nodes.values()))['known'])
        self.assertEqual(seed_anchors(work), [])

    def test_resumes_exact_cursor_without_repeating_first_page(self):
        graph=CandidateGraph({'papers':[]});client=Mock()
        client._fetch.return_value={'url':'https://api.openalex.org/works','retrieved_at':'2026-11-07',
            'payload':{'results':[{'id':'https://openalex.org/W3','title':'Bitcoin fees'}],'meta':{'next_cursor':None}}}
        collect(client,graph,'openalex','author:A1',{'filter':'authorships.author.id:A1'},1,start_cursor='saved-next')
        self.assertEqual(client._fetch.call_args.args[1]['cursor'],'saved-next')
        self.assertTrue(graph.coverage[0]['complete']);self.assertEqual(graph.coverage[0]['start_cursor'],'saved-next')

    def test_seed_with_only_linked_version_identifier_can_be_discovered(self):
        work = {"source_ids": {"crossref": "10.1145/3419614.3423254"},
                "versions": [{"source_ids": {"openalex": "W3037803706"}},
                             {"source_ids": {"openalex": "invalid"}},
                             {"source_ids": {"openalex": None}}],
                "publications": [{"source_ids": {"openalex": "W3037803706"}}]}
        self.assertEqual(seed_anchors(work), ["W3037803706"])

    def test_proceedings_join_uses_exact_doi_and_retains_dblp_evidence(self):
        graph = CandidateGraph({"papers": []})
        graph.add({"source": "dblp", "source_id": "conf/aft/test", "title": "Mechanisms",
                   "doi": "10.1234/test"}, "proceedings:db/conf/aft/aft2024.bht")
        client = Mock()
        client._fetch.return_value = {"url": "https://api.openalex.org/works", "retrieved_at": "2026-11-06", "payload": {
            "results": [{"id": "https://openalex.org/W3", "doi": "https://doi.org/10.1234/test", "title": "Mechanisms"}],
            "meta": {"next_cursor": None}}}
        hydrate_dblp(client, graph)
        self.assertEqual(client._fetch.call_args.args[1]["filter"], "doi:10.1234/test")
        self.assertEqual(len(graph.nodes), 1)
        self.assertEqual({r["source"] for r in next(iter(graph.nodes.values()))["sources"].values()}, {"dblp", "openalex"})

    def test_keeps_first_page_if_index_requires_authentication_to_continue(self):
        graph = CandidateGraph({"papers": []})
        client = Mock()
        client._fetch.side_effect = [
            {"url": "https://api.openalex.org/works", "retrieved_at": "2026-11-06", "payload": {
                "results": [{"id": "https://openalex.org/W3", "title": "Bitcoin transaction fee mechanisms"}],
                "meta": {"next_cursor": "next"},
            }},
            MetadataError("http_401"),
        ]
        collect(client, graph, "openalex", "citations:gs-003", {"filter": "cites:W1"}, 2, cites="gs-003")
        snapshot = graph.snapshot()
        self.assertEqual(snapshot["coverage"][0]["records"], 1)
        self.assertFalse(snapshot["coverage"][0]["complete"])
        self.assertEqual(snapshot["coverage"][0]["next_cursor"], "next")
        self.assertEqual(snapshot["edges"][0]["to"], "gs-003")
        self.assertEqual(snapshot["review_queue"][0]["connected_seeds"], ["gs-003"])

    def test_two_seeds_can_surface_candidate_with_no_title_hit(self):
        graph = CandidateGraph({"papers": []})
        candidate = {"source": "dblp", "source_id": "conf/ec/Example", "title": "A market design problem"}
        key = graph.add(candidate, "proceedings:example")
        graph.edges.update([(key, "gs-002"), ("gs-003", key)])
        self.assertEqual(graph.snapshot()["review_queue"], [
            {"id": key, "topic_hints": [], "connected_seeds": ["gs-002", "gs-003"]},
        ])
