"""Golden Seeds integrity and identifier-based projection regression checks."""

from collections import Counter
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build import EVIDENCE, LEDGER, OUTPUT, SEEDS, project
from directory import append_work, new_directory, read_json, validate_directory, write_json


class GoldenSeedTests(unittest.TestCase):
    def test_editorial_topics_preserve_original_seed_classification(self):
        seeds=read_json(SEEDS)
        d=project(seeds,read_json(EVIDENCE))
        self.assertEqual(seeds['papers'][-1]['topic_ids'],['rational-cryptography'])
        self.assertEqual(set(next(p for p in d['papers'] if p['id']=='gs-050')['legacy_topic_ids']),{'tfm','rational-cryptography'})

    def test_original_lines_and_topic_counts(self):
        seeds = read_json(SEEDS)
        raw = (SEEDS.parent / "golden_seeds_original.md").read_text(encoding="utf-8")
        counts = Counter(topic for paper in seeds["papers"] for topic in paper["topic_ids"])
        self.assertEqual([counts[topic["id"]] for topic in seeds["topics"]], [5, 6, 5, 6, 6, 6, 5, 6, 5])
        for seed in seeds["papers"]:
            self.assertIn(seed["raw_citation"], raw.splitlines())

    def test_committed_projection_is_reproducible(self):
        ledger = read_json(LEDGER) if LEDGER.exists() else None
        self.assertEqual(project(read_json(SEEDS), read_json(EVIDENCE), ledger), read_json(OUTPUT))

    def test_accepted_ledger_rebuilds_after_seed_projection(self):
        seeds = read_json(SEEDS)
        evidence = read_json(EVIDENCE)
        record = {
            "work_id": "discovered-test",
            "topic_ids": ["tfm"],
            "verification": {"status": "verified", "metadata": {"title": "New verified work"}},
            "raw_input": {"title": "New verified work", "source": "openalex"},
        }
        staged = project(seeds, evidence)
        append_work(staged, **record)
        staged["papers"][-1].update(venue_tag=None, topic_ids=["tfm-design"], legacy_topic_ids=["tfm"])
        self.assertEqual(project(seeds, evidence, {"schema_version": 1, "records": [record]}), staged)


class DirectoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = new_directory([{"id": "tfm", "name": "TFM"}])

    def add(self, work_id, metadata=None, versions=None):
        return append_work(
            self.directory, work_id=work_id, topic_ids=["tfm"],
            raw_input={"title": "User title", "year": 1901, "authors": ["Doe"]},
            verification={
                "status": "partial" if metadata else "unverified",
                "metadata": metadata, "versions": versions,
            },
        )

    def test_hints_remain_separate(self):
        paper = self.add("unverified")
        self.assertIsNone(paper["year"])
        self.assertEqual(paper["authors"], [])
        self.assertEqual(paper["raw_input"]["year"], 1901)
        validate_directory(self.directory)

    def test_shared_identifiers_link_people_and_keep_affiliation_observations(self):
        first = self.add("one", {
            "title": "One", "year": 2001, "source_ids": {"openalex": "W101"},
            "authors": [
                {"name": "Jane Doe", "ids": {"openalex": "A1"}, "institutions": [
                    {"name": "University A", "ids": {"openalex": "I1"}},
                ]},
                {"name": "Jane Doe", "ids": {"openalex": "A2"}},
            ],
        })
        second = self.add("two", {
            "title": "Two", "year": 2002, "source_ids": {"openalex": "W102"},
            "authors": [
                {"name": "Jane M. Doe", "ids": {"openalex": "A1"}, "institutions": [
                    {"name": "University B", "ids": {"openalex": "I2"}},
                ]},
                {"name": "John Doe", "ids": {}},
            ],
        })
        self.assertEqual(len(self.directory["researchers"]), 2)
        self.assertEqual(second["researcher_ids"], first["researcher_ids"][:1])
        self.assertEqual(len(self.directory["researchers"][0]["affiliation_ids"]), 2)
        self.assertEqual(
            [entry["year"] for entry in self.directory["researchers"][0]["affiliation_evidence"]],
            [2001, 2002],
        )
        self.assertIn("John Doe", second["authors"])
        validate_directory(self.directory)

    def test_duplicate_version_identifier_stops_build(self):
        self.add("one", {"title": "One"}, [{"doi": "10.1000/test"}])
        self.add("two", {"title": "Two", "doi": "10.1000/TEST"})
        with self.assertRaisesRegex(ValueError, "shared work identifier"):
            validate_directory(self.directory)

    def test_failed_atomic_write_keeps_last_document(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder) / "snapshot.json"
            write_json(path, {"first": True})
            with patch("directory.os.replace", side_effect=OSError("write failed")):
                with self.assertRaises(OSError):
                    write_json(path, {"first": False})
            self.assertEqual(read_json(path), {"first": True})
            self.assertEqual(list(Path(folder).iterdir()), [path])


if __name__ == "__main__":
    unittest.main()
