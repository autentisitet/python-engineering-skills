#!/usr/bin/env python3
"""Verify the cross-check comparison logic without invoking the model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from scripts.evals import cross_check_evals
from scripts.evals.validate_evals import case_sha256


class ErrorDetectionTests(unittest.TestCase):
    def test_fail_is_an_error_for_either_label(self) -> None:
        self.assertIs(
            cross_check_evals.trial_outcome({"status": "fail"}, True),
            cross_check_evals.Outcome.ERROR,
        )
        self.assertIs(
            cross_check_evals.trial_outcome({"status": "fail"}, False),
            cross_check_evals.Outcome.ERROR,
        )

    def test_positive_miss_without_infrastructure_is_an_error(self) -> None:
        trial = {"status": "inconclusive", "turn_completed": True}
        self.assertIs(
            cross_check_evals.trial_outcome(trial, True), cross_check_evals.Outcome.ERROR
        )
        self.assertIs(
            cross_check_evals.trial_outcome(trial, False),
            cross_check_evals.Outcome.UNDETERMINED,
        )

    def test_infrastructure_inconclusive_is_not_an_error(self) -> None:
        for trial in (
            {"status": "inconclusive", "reason": "timeout", "turn_completed": False},
            {"status": "inconclusive", "reason": "agent_process_failed", "turn_completed": False},
        ):
            with self.subTest(trial=trial):
                self.assertIs(
                    cross_check_evals.trial_outcome(trial, True),
                    cross_check_evals.Outcome.UNDETERMINED,
                )

    def test_pass_is_not_an_error(self) -> None:
        self.assertIs(
            cross_check_evals.trial_outcome({"status": "pass"}, True),
            cross_check_evals.Outcome.PASS,
        )

    def test_baseline_error_ids_collects_error_cases(self) -> None:
        result = {"results": [
            {"id": "a-pos-1", "skill": "a", "should_trigger": True, "trials": [
                {"status": "pass"}, {"status": "fail"},
            ]},
            {"id": "a-neg-1", "skill": "a", "should_trigger": False, "trials": [
                {"status": "pass"},
            ]},
            {"id": "a-pos-2", "skill": "a", "should_trigger": True, "trials": [
                {"status": "inconclusive", "turn_completed": True},
            ]},
        ]}
        self.assertEqual(cross_check_evals.baseline_error_ids(result), {"a-pos-1", "a-pos-2"})


class LabelTests(unittest.TestCase):
    def test_case_label_aggregates_trials(self) -> None:
        cases = (
            ({"trials": [{"status": "pass"}, {"status": "pass"}]}, cross_check_evals.Outcome.PASS),
            ({"trials": [{"status": "pass"}, {"status": "fail"}]}, cross_check_evals.Outcome.ERROR),
            ({"trials": [{"status": "inconclusive", "reason": "timeout"}]}, cross_check_evals.Outcome.UNDETERMINED),
            ({"trials": []}, cross_check_evals.Outcome.UNKNOWN),
        )
        for row, expected in cases:
            with self.subTest(expected=expected):
                self.assertIs(cross_check_evals.case_outcome(row), expected)


class CompareTests(unittest.TestCase):
    def setUp(self) -> None:
        self.baseline = {"results": [
            {"id": "a-pos-1", "skill": "a", "should_trigger": True, "trials": [
                {"status": "inconclusive", "turn_completed": True},
            ]},
            {"id": "a-neg-1", "skill": "a", "should_trigger": False, "trials": [
                {"status": "fail"},
            ]},
            {"id": "a-neg-2", "skill": "a", "should_trigger": False, "trials": [
                {"status": "pass"},
            ]},
        ]}
        self.queries = {
            "a-pos-1": {"query": "positive miss"},
            "a-neg-1": {"query": "false positive"},
            "a-neg-2": {"query": "true negative"},
        }

    def test_resolved_persisted_and_introduced_are_bucketed(self) -> None:
        new = {"results": [
            {"id": "a-pos-1", "skill": "a", "should_trigger": True, "trials": [
                {"status": "pass"},
            ]},
            {"id": "a-neg-1", "skill": "a", "should_trigger": False, "trials": [
                {"status": "fail"},
            ]},
            {"id": "a-neg-2", "skill": "a", "should_trigger": False, "trials": [
                {"status": "fail"},
            ]},
        ]}
        diff = cross_check_evals.compare_runs(self.baseline, new, self.queries)
        self.assertEqual([record["id"] for record in diff["resolved"]], ["a-pos-1"])
        self.assertEqual([record["id"] for record in diff["persisted"]], ["a-neg-1"])
        self.assertEqual([record["id"] for record in diff["introduced"]], ["a-neg-2"])
        self.assertEqual(diff["unresolved"], [])

    def test_undetermined_new_trial_is_unresolved(self) -> None:
        new = {"results": [
            {"id": "a-pos-1", "skill": "a", "should_trigger": True, "trials": [
                {"status": "inconclusive", "reason": "timeout"},
            ]},
        ]}
        diff = cross_check_evals.compare_runs(self.baseline, new, self.queries)
        self.assertEqual(diff["resolved"], [])
        self.assertEqual([record["id"] for record in diff["unresolved"]], ["a-pos-1"])


class SubsetDatasetTests(unittest.TestCase):
    def test_subset_keeps_envelope_and_filters_queries(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "cases.json"
            source.write_text(json.dumps({
                "version": 1,
                "split": "validation",
                "split_seed": 20261112,
                "queries": [
                    {"id": "a-pos-1", "skill": "a", "category": "direct",
                     "query": "keep me", "should_trigger": True},
                    {"id": "a-pos-2", "skill": "a", "category": "direct",
                     "query": "drop me", "should_trigger": True},
                ],
            }), encoding="utf-8")
            target = root / "subset.json"
            cross_check_evals.build_subset_dataset(source, {"a-pos-1"}, target)
            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(data["split"], "validation")
            self.assertEqual([query["id"] for query in data["queries"]], ["a-pos-1"])


class BaselineQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.case = {"id": "a-positive-01", "skill": "a", "category": "direct",
                     "query": "Use a.", "should_trigger": True}

    def test_query_change_is_detected_even_when_id_is_unchanged(self) -> None:
        baseline = {"results": [{"id": self.case["id"],
                                 "case_sha256": case_sha256(self.case)}]}
        changed = dict(self.case, query="Different question.")
        self.assertEqual(cross_check_evals.baseline_query_mismatches(
            baseline, [changed], "new-dataset-sha"
        ), [self.case["id"]])

    def test_legacy_baseline_needs_matching_full_dataset_sha(self) -> None:
        baseline = {"dataset_sha256": "matching", "results": [{"id": self.case["id"]}]}
        self.assertEqual(cross_check_evals.baseline_query_mismatches(
            baseline, [self.case], "matching"
        ), [])
        self.assertEqual(cross_check_evals.baseline_query_mismatches(
            baseline, [self.case], "changed"
        ), [self.case["id"]])

    def test_main_rejects_changed_query_before_model_calls(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dataset = root / "dataset.json"
            dataset.write_text(json.dumps({"queries": [dict(self.case, query="Changed.")]}),
                               encoding="utf-8")
            baseline = root / "baseline.json"
            baseline.write_text(json.dumps({"results": [{"id": self.case["id"],
                "case_sha256": case_sha256(self.case), "should_trigger": True,
                "trials": [{"status": "fail"}]}]}), encoding="utf-8")
            argv = ["cross_check_evals", "--baseline", str(baseline), "--dataset",
                    str(dataset), "--model", "test-model", "--allow-model-calls",
                    "--output", str(root / "output.json")]
            with mock.patch.object(sys, "argv", argv), \
                    mock.patch.object(cross_check_evals, "run_evals") as run_evals, \
                    self.assertRaises(SystemExit) as error:
                cross_check_evals.main()
            self.assertEqual(error.exception.code, 2)
            run_evals.assert_not_called()


class RunnerArgumentTests(unittest.TestCase):
    def test_optional_and_repeatable_arguments_are_forwarded(self) -> None:
        args = argparse.Namespace(
            runs=2,
            jobs=1,
            timeout=30,
            profile="profile-a",
            model="model-a",
            reasoning_effort="low",
            pass_env=["PROVIDER_TOKEN"],
        )
        captured: list[str] = []

        def capture() -> int:
            captured.extend(sys.argv)
            return 0

        with mock.patch.object(cross_check_evals.activation, "main", side_effect=capture):
            self.assertEqual(
                cross_check_evals.run_evals(Path("cases.json"), Path("result.json"), args), 0
            )

        self.assertIn("profile-a", captured)
        self.assertIn("model-a", captured)
        self.assertEqual(captured[captured.index("--pass-env") + 1], "PROVIDER_TOKEN")
        self.assertNotIn("--use-user-config", captured)


if __name__ == "__main__":
    unittest.main()
