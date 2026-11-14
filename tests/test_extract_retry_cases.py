#!/usr/bin/env python3
"""Verify retry-dataset extraction from activation results."""

from __future__ import annotations

import unittest

from scripts.evals import extract_retry_cases


class ExtractRetryCasesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = {
            "version": 1,
            "split": "validation",
            "split_seed": 20261112,
            "queries": [
                {"id": "a-positive-01", "skill": "a", "category": "direct",
                 "query": "Use a.", "should_trigger": True},
                {"id": "a-negative-01", "skill": "a", "category": "boundary",
                 "query": "Skip a.", "should_trigger": False},
                {"id": "b-positive-01", "skill": "b", "category": "direct",
                 "query": "Use b.", "should_trigger": True},
            ],
        }

    def test_selects_only_matching_inconclusive_reason(self) -> None:
        result = {"results": [
            {"id": "a-positive-01", "skill": "a", "should_trigger": True,
             "trials": [{"status": "inconclusive", "reason": "timeout"}]},
            {"id": "a-negative-01", "skill": "a", "should_trigger": False,
             "trials": [{"status": "pass"}]},
            {"id": "b-positive-01", "skill": "b", "should_trigger": True,
             "trials": [{"status": "inconclusive", "reason": "agent_process_failed"}]},
        ]}
        selected, missing = extract_retry_cases.extract_cases(result, self.source, "timeout")
        self.assertEqual([case["id"] for case in selected], ["a-positive-01"])
        self.assertEqual(missing, [])

    def test_any_inconclusive_selects_reasonless_trials(self) -> None:
        result = {"results": [
            {"id": "a-positive-01", "skill": "a", "should_trigger": True,
             "trials": [{"status": "inconclusive", "reason": None}]},
        ]}
        selected, _ = extract_retry_cases.extract_cases(result, self.source, None)
        self.assertEqual([case["id"] for case in selected], ["a-positive-01"])

    def test_unknown_result_ids_are_reported(self) -> None:
        result = {"results": [
            {"id": "unknown-positive-01", "skill": "a", "should_trigger": True,
             "trials": [{"status": "inconclusive", "reason": "timeout"}]},
        ]}
        selected, missing = extract_retry_cases.extract_cases(result, self.source, "timeout")
        self.assertEqual(selected, [])
        self.assertEqual(missing, ["unknown-positive-01"])


if __name__ == "__main__":
    unittest.main()
