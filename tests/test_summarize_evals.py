#!/usr/bin/env python3
"""Verify that eval summaries are derived deterministically from runner output."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts.evals import summarize_evals
from scripts.evals.validate_evals import case_sha256


class ClassifyTests(unittest.TestCase):
    def test_routing_outcomes_are_classified(self) -> None:
        self.assertEqual(summarize_evals.classify({"status": "pass"}, True), "tp")
        self.assertEqual(summarize_evals.classify({"status": "pass"}, False), "tn")
        self.assertEqual(summarize_evals.classify({"status": "fail"}, False), "fp")
        self.assertEqual(
            summarize_evals.classify(
                {"status": "inconclusive", "infrastructure_failure": True, "reason": "timeout"}, True
            ),
            "inc_pos",
        )

    def test_positive_miss_without_infrastructure_is_a_false_negative(self) -> None:
        trial = {"status": "inconclusive", "observed_skill_read": False, "turn_completed": True}
        self.assertEqual(summarize_evals.classify(trial, True), "fn")
        self.assertEqual(summarize_evals.classify(trial, False), "inc_neg")


class SummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = {
            "evaluation_kind": "observed_entrypoint_reads",
            "results": [
                {"id": "a-pos-1", "skill": "a", "should_trigger": True, "trials": [
                    {"status": "pass", "observed_skill_read": True},
                    {"status": "inconclusive", "observed_skill_read": False, "turn_completed": True},
                ]},
                {"id": "a-neg-1", "skill": "a", "should_trigger": False, "trials": [
                    {"status": "pass", "observed_skill_read": False},
                    {"status": "fail", "observed_skill_read": True},
                ]},
                {"id": "a-pos-2", "skill": "a", "should_trigger": True, "trials": [
                    {"status": "inconclusive", "infrastructure_failure": True, "reason": "timeout"},
                ]},
                {"id": "a-neg-2", "skill": "a", "should_trigger": False, "trials": [
                    {"status": "inconclusive", "infrastructure_failure": True, "reason": "timeout"},
                ]},
            ],
        }

    def test_overall_metrics_exclude_inconclusive_from_denominators(self) -> None:
        summary = summarize_evals.compute_summary(self.result)
        overall = summary["overall"]
        self.assertEqual(overall["tp"], 1)
        self.assertEqual(overall["fn"], 1)
        self.assertEqual(overall["fp"], 1)
        self.assertEqual(overall["tn"], 1)
        self.assertEqual(overall["inconclusive_total"], 2)
        self.assertEqual(overall["total_trials"], 6)
        self.assertEqual(overall["precision"], 0.5)
        self.assertEqual(overall["recall"], 0.5)
        self.assertEqual(overall["f1"], 0.5)
        self.assertEqual(overall["accuracy"], 0.5)
        self.assertEqual(overall["false_positive_rate"], 0.5)
        self.assertEqual(overall["false_negative_rate"], 0.5)
        self.assertEqual(overall["specificity"], 0.5)
        self.assertEqual(overall["balanced_accuracy"], 0.5)
        self.assertEqual(overall["coverage"], 0.6667)
        self.assertAlmostEqual(overall["inconclusive_rate"], 0.3333, places=4)

    def test_per_skill_matches_overall_for_a_single_skill(self) -> None:
        summary = summarize_evals.compute_summary(self.result)
        per_skill = summary["per_skill"]["a"]
        overall = summary["overall"]
        for key in ("tp", "fn", "fp", "tn", "precision", "recall", "f1", "accuracy"):
            self.assertEqual(per_skill[key], overall[key])
        self.assertEqual(per_skill["inconclusive"], 2)

    def test_duration_metrics_cover_each_session_and_skill(self) -> None:
        result = {
            "results": [
                {"id": "a-pos-1", "skill": "a", "should_trigger": True, "trials": [
                    {"status": "pass", "duration_seconds": 2.0,
                     "usage": {"input_tokens": 10, "cached_input_tokens": 4, "output_tokens": 2}},
                    {"status": "pass", "duration_seconds": 4.0,
                     "usage": {"input_tokens": 20, "cached_input_tokens": 8, "output_tokens": 4}},
                ]},
                {"id": "b-pos-1", "skill": "b", "should_trigger": True, "trials": [
                    {"status": "pass", "duration_seconds": 6.0,
                     "usage": {"input_tokens": 30, "cached_input_tokens": 0, "output_tokens": 6}},
                ]},
            ]
        }
        summary = summarize_evals.compute_summary(result)
        overall = summary["overall"]
        self.assertEqual(overall["session_count"], 3)
        self.assertEqual(overall["duration_seconds_mean"], 4.0)
        self.assertEqual(overall["duration_seconds_total"], 12.0)
        self.assertEqual(overall["duration_seconds_min"], 2.0)
        self.assertEqual(overall["duration_seconds_max"], 6.0)
        self.assertEqual(overall["duration_seconds_p50"], 4.0)
        self.assertEqual(overall["duration_seconds_p95"], 5.8)
        self.assertEqual(summary["per_skill"]["a"]["duration_seconds_mean"], 3.0)
        self.assertEqual(overall["input_tokens_total"], 60)
        self.assertEqual(overall["cached_input_tokens_total"], 12)
        self.assertEqual(overall["output_tokens_total"], 12)
        self.assertEqual(overall["total_tokens"], 72)
        self.assertEqual(overall["tokens_per_second"], 6.0)
        self.assertEqual(summary["per_skill"]["a"]["total_tokens"], 36)
        self.assertEqual(summary["per_skill"]["b"]["tokens_per_second"], 6.0)
        self.assertEqual(summary["per_skill"]["a"]["session_count"], 2)
        self.assertEqual(summary["per_skill"]["b"]["duration_seconds_mean"], 6.0)

    def test_zero_precision_and_recall_produce_zero_f1(self) -> None:
        result = {"results": [
            {"id": "a-pos", "skill": "a", "category": "direct", "should_trigger": True,
             "trials": [{"status": "fail", "observed_skill_read": False}]},
            {"id": "a-neg", "skill": "a", "category": "boundary", "should_trigger": False,
             "trials": [{"status": "pass", "observed_skill_read": False}]},
        ]}
        overall = summarize_evals.compute_summary(result)["overall"]
        self.assertEqual(overall["precision"], None)
        self.assertEqual(overall["recall"], 0.0)
        self.assertEqual(overall["f1"], None)
        self.assertEqual(overall["specificity"], 1.0)

        self.assertEqual(summarize_evals.metrics(0, 1, 1, 0)["f1"], 0.0)

    def test_query_trigger_rates_and_category_metrics_are_reported(self) -> None:
        result = {"results": [
            {"id": "a-pos", "skill": "a", "category": "direct", "should_trigger": True,
             "trials": [
                 {"status": "pass", "observed_skill_read": True},
                 {"status": "inconclusive", "infrastructure_failure": True},
             ]},
            {"id": "a-neg", "skill": "a", "category": "boundary", "should_trigger": False,
             "trials": [{"status": "pass", "observed_skill_read": False}]},
        ]}
        summary = summarize_evals.compute_summary(result)
        direct = summary["per_category"]["direct"]
        self.assertEqual(direct["recall"], 1.0)
        self.assertEqual(direct["coverage"], 0.5)
        query = summary["per_query"][0]
        self.assertEqual(query["valid_trials"], 1)
        self.assertEqual(query["trigger_rate"], 1.0)
        self.assertEqual(query["coverage"], 0.5)

    def test_inconclusive_reasons_are_reported(self) -> None:
        reasons = summarize_evals.compute_summary(self.result)["inconclusive_reasons"]
        self.assertEqual(reasons, {"timeout": 2})

    def test_freshness_detects_current_and_stale_digests(self) -> None:
        current = summarize_evals.skills_digest()
        with mock.patch.object(summarize_evals, "skills_digest", return_value=current):
            freshness = summarize_evals.result_freshness({"skills_sha256": current})
            stale = summarize_evals.result_freshness({"skills_sha256": "old"})
        self.assertTrue(freshness["skills_current"])
        self.assertFalse(stale["skills_current"])
        self.assertIsNone(freshness["dataset_current"])

    def test_subset_freshness_uses_matching_case_hashes(self) -> None:
        case = {"id": "a-positive-01", "skill": "a", "category": "direct",
                "query": "Use a.", "should_trigger": True}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dataset = root / "evals" / "train_queries.json"
            dataset.parent.mkdir()
            dataset.write_text(json.dumps({"version": 1, "split": "train",
                                           "split_seed": 42, "queries": [case]}), encoding="utf-8")
            subset_sha = hashlib.sha256(b"subset differs from complete JSON").hexdigest()
            result = {"dataset_split": "train", "dataset_sha256": subset_sha,
                      "results": [{"id": case["id"], "case_sha256": case_sha256(case)}]}
            with mock.patch.object(summarize_evals, "ROOT", root):
                self.assertTrue(summarize_evals.result_freshness(result)["dataset_current"])
                changed = dict(case, query="Different question.")
                dataset.write_text(json.dumps({"version": 1, "split": "train",
                                               "split_seed": 42, "queries": [changed]}),
                                   encoding="utf-8")
                self.assertFalse(summarize_evals.result_freshness(result)["dataset_current"])
                unknown = dict(result, results=[{"id": "unrelated",
                                                 "case_sha256": case_sha256(case)}])
                self.assertIsNone(summarize_evals.result_freshness(unknown)["dataset_current"])

    def test_skill_digest_ignores_generated_cache_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            entry = root / "skills" / "sample" / "SKILL.md"
            entry.parent.mkdir(parents=True)
            entry.write_text("# Sample\n", encoding="utf-8")
            initial = summarize_evals.skills_digest(root)
            cache = entry.parent / "__pycache__" / "sample.pyc"
            cache.parent.mkdir()
            cache.write_bytes(b"generated")
            self.assertEqual(summarize_evals.skills_digest(root), initial)
            entry.write_text("# Changed\n", encoding="utf-8")
            self.assertNotEqual(summarize_evals.skills_digest(root), initial)

    def test_train_validation_gap_uses_split_metadata(self) -> None:
        train = summarize_evals.compute_summary({
            "dataset_split": "train",
            "results": [
                {"id": "p", "skill": "a", "category": "direct", "should_trigger": True,
                 "trials": [{"status": "pass", "observed_skill_read": True}]},
                {"id": "n", "skill": "a", "category": "boundary", "should_trigger": False,
                 "trials": [{"status": "pass", "observed_skill_read": False}]},
            ],
        })
        validation = summarize_evals.compute_summary({
            "dataset_split": "validation",
            "results": [
                {"id": "p", "skill": "a", "category": "direct", "should_trigger": True,
                 "trials": [{"status": "fail", "observed_skill_read": False}]},
                {"id": "n", "skill": "a", "category": "boundary", "should_trigger": False,
                 "trials": [{"status": "pass", "observed_skill_read": False}]},
            ],
        })
        gap = summarize_evals.train_validation_gap([train, validation])
        self.assertIsNotNone(gap)
        self.assertEqual(gap["recall_gap"], 1.0)
        self.assertEqual(gap["accuracy_gap"], 0.5)

    def test_percentile_interpolates_and_handles_empty_values(self) -> None:
        self.assertEqual(summarize_evals.percentile([2.0, 4.0, 6.0], 0.95), 5.8)
        self.assertIsNone(summarize_evals.percentile([], 0.95))


if __name__ == "__main__":
    unittest.main()
