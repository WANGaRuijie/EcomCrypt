import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from directory import ledger_text, read_json, write_ledger


class LedgerFormatTest(unittest.TestCase):
    def test_round_trip_keeps_every_field(self):
        ledger = {"schema_version": 1, "records": [{"work_id": "a", "raw_input": {"title": "Ä \"q\""}}, {"work_id": "b", "topic_ids": []}]}
        self.assertEqual(json.loads(ledger_text(ledger)), ledger)

    def test_one_record_per_line(self):
        ledger = {"schema_version": 1, "records": [{"work_id": "a"}, {"work_id": "b"}]}
        lines = ledger_text(ledger).splitlines()
        self.assertEqual(lines, ['{"schema_version":1,"records":[', '{"work_id":"a"},', '{"work_id":"b"}', "]}"])

    def test_empty_ledger(self):
        for ledger in ({"schema_version": 1, "records": []}, {"records": []}):
            self.assertEqual(json.loads(ledger_text(ledger)), ledger)

    def test_write_ledger_replaces_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "ledger.json"
            ledger = {"schema_version": 1, "records": [{"work_id": "a"}]}
            write_ledger(path, ledger)
            self.assertEqual(read_json(path), ledger)


if __name__ == "__main__":
    unittest.main()
