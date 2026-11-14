#!/usr/bin/env python3
"""Verify JSON <-> CSV conversion for eval query sets."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from scripts.evals import convert_queries


ROOT = Path(__file__).resolve().parents[1]


class ConvertQueriesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make_json(self, path: Path, queries: list[dict]) -> None:
        path.write_text(json.dumps({
            "version": 1,
            "split": "train",
            "split_seed": 20261112,
            "queries": queries,
        }, indent=2), encoding="utf-8")

    def test_round_trip_preserves_queries(self) -> None:
        queries = [
            {
                "id": "sample-skill-positive-01",
                "skill": "sample-skill",
                "category": "direct",
                "query": "Use the sample skill, with a comma and \"quotes\".",
                "should_trigger": True,
            },
            {
                "id": "sample-skill-negative-01",
                "skill": "sample-skill",
                "category": "boundary",
                "query": "Skip the sample skill.",
                "should_trigger": False,
            },
        ]
        json_path = self.root / "queries.json"
        csv_path = self.root / "queries.csv"
        self.make_json(json_path, queries)

        convert_queries.write_csv(csv_path, convert_queries.read_json_queries(json_path))
        rebuilt = convert_queries.read_csv_queries(csv_path)
        self.assertEqual(rebuilt, queries)

    def test_csv_uses_excel_friendly_utf8_bom_and_boolean_words(self) -> None:
        csv_path = self.root / "queries.csv"
        convert_queries.write_csv(csv_path, [{
            "id": "sample-skill-positive-01",
            "skill": "sample-skill",
            "category": "direct",
            "query": "Use the sample skill.",
            "should_trigger": True,
        }])
        raw = csv_path.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows[0]["should_trigger"], "true")

    def test_excel_formula_prefixes_are_escaped_and_round_trip(self) -> None:
        queries = [
            {
                "id": "sample-skill-positive-01",
                "skill": "sample-skill",
                "category": "direct",
                "query": value,
                "should_trigger": True,
            }
            for value in ("=CMD()", "+1", "-1", "@SUM(A1)", "\tformula", "'=literal")
        ]
        csv_path = self.root / "queries.csv"
        convert_queries.write_csv(csv_path, queries)
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            exported = list(csv.DictReader(handle))
        self.assertTrue(all(row["query"].startswith("'") for row in exported))
        self.assertEqual(convert_queries.read_csv_queries(csv_path), queries)

    def test_parse_bool_accepts_common_true_false_spellings(self) -> None:
        for value in ("true", "1", "yes", "TRUE"):
            self.assertTrue(convert_queries.parse_bool(value))
        for value in ("false", "0", "no", "FALSE"):
            self.assertFalse(convert_queries.parse_bool(value))
        with self.assertRaises(ValueError):
            convert_queries.parse_bool("maybe")

    def test_missing_csv_header_is_rejected(self) -> None:
        csv_path = self.root / "queries.csv"
        csv_path.write_text("id,skill\nx,y\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            convert_queries.read_csv_queries(csv_path)

    def test_write_json_is_atomic_and_skips_unchanged_content(self) -> None:
        destination = self.root / "queries.json"
        queries = [{
            "id": "sample-skill-positive-01",
            "skill": "sample-skill",
            "category": "direct",
            "query": "Use the sample skill.",
            "should_trigger": True,
        }]
        self.assertTrue(convert_queries.write_json(destination, queries, 1, "train", 20261112))
        first_bytes = destination.read_bytes()
        self.assertFalse(convert_queries.write_json(destination, queries, 1, "train", 20261112))
        self.assertEqual(destination.read_bytes(), first_bytes)

        queries[0]["query"] = "Updated query."
        self.assertTrue(convert_queries.write_json(destination, queries, 1, "train", 20261112))
        self.assertNotEqual(destination.read_bytes(), first_bytes)

    def test_committed_csv_files_match_json_sources(self) -> None:
        for stem in ("train_queries", "validation_queries"):
            with self.subTest(stem=stem):
                json_queries = convert_queries.read_json_queries(ROOT / "evals" / f"{stem}.json")
                csv_queries = convert_queries.read_csv_queries(ROOT / "evals" / f"{stem}.csv")
                self.assertEqual(csv_queries, json_queries)


if __name__ == "__main__":
    unittest.main()
