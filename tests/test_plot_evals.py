#!/usr/bin/env python3
"""Smoke-test chart generation from activation result files."""

from __future__ import annotations

import json
import hashlib
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from scripts.evals import plot_evals


class PlotEvalsTests(unittest.TestCase):
    def test_renders_nonempty_pngs_for_both_splits(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            files = []
            for split in ("train", "validation"):
                path = root / f"{split}.json"
                path.write_text(json.dumps({
                    "dataset_split": split,
                    "results": [
                        {"id": "positive", "skill": "sample", "category": "direct",
                         "should_trigger": True, "trials": [
                             {"status": "pass", "observed_skill_read": True,
                              "duration_seconds": 1.0},
                         ]},
                        {"id": "negative", "skill": "sample", "category": "boundary",
                         "should_trigger": False, "trials": [
                             {"status": "pass", "observed_skill_read": False,
                              "duration_seconds": 2.0},
                         ]},
                    ],
                }), encoding="utf-8")
                files.append(path)
            output = root / "charts"
            argv = ["plot_evals", *(str(path) for path in files),
                    "--output-dir", str(output), "--prefix", "test"]
            with mock.patch.dict(os.environ, {"MPLCONFIGDIR": str(root / "mplconfig")}), \
                    mock.patch.object(sys, "argv", argv):
                self.assertEqual(plot_evals.main(), 0)
            expected = {f"test-{name}.png" for name in (
                "confusion", "per-skill", "overall", "radar", "latency", "train-validation",
                "train-validation-per-skill",
            )}
            self.assertEqual({path.name for path in output.iterdir()}, expected)
            for path in output.iterdir():
                with self.subTest(path=path.name):
                    self.assertTrue(path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
                    self.assertGreater(path.stat().st_size, 100)

    def test_legacy_split_is_inferred_only_from_matching_dataset_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dataset = root / "evals" / "train_queries.json"
            dataset.parent.mkdir()
            dataset.write_text('{"split":"train"}', encoding="utf-8")
            digest = hashlib.sha256(dataset.read_bytes()).hexdigest()
            with mock.patch.object(plot_evals, "ROOT", root):
                summary = {"metadata": {"dataset_split": None, "dataset_sha256": digest}}
                self.assertEqual(plot_evals.split_name(summary), "train")
                summary["metadata"]["dataset_sha256"] = "other digest"
                self.assertIsNone(plot_evals.split_name(summary))

    def test_trend_requires_same_split_dataset_and_runtime(self) -> None:
        base = {"metadata": {"dataset_split": "train", "dataset_sha256": "dataset",
                             "codex_version": "codex-cli test", "codex_options_sha256": "options"}}
        other = {"metadata": dict(base["metadata"])}
        entries = [("one.json", base), ("two.json", other)]
        self.assertTrue(plot_evals.comparable_iterations(entries))
        for key, changed in (("dataset_split", "validation"), ("dataset_sha256", "updated"),
                             ("codex_options_sha256", "other"), ("codex_version", None)):
            with self.subTest(key=key):
                other["metadata"][key] = changed
                self.assertFalse(plot_evals.comparable_iterations(entries))
                other["metadata"][key] = base["metadata"][key]

    def test_undefined_overall_score_is_labeled_na_not_zero(self) -> None:
        import matplotlib.pyplot as plt

        summary = {"overall": {"precision": None, "recall": 0.0, "specificity": 1.0,
                               "f1": None, "accuracy": 0.5, "coverage": 1.0}}
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "overall.png"
            with mock.patch.object(plt, "close"):
                plot_evals.overall_metrics(summary, output)
                ax = plt.gcf().axes[0]
                self.assertTrue(math.isnan(ax.patches[0].get_height()))
                self.assertEqual(ax.patches[1].get_height(), 0.0)
                self.assertEqual([text.get_text() for text in ax.texts].count("N/A"), 2)
            plt.close("all")

    def test_split_comparison_labels_scores_denominators_and_errors(self) -> None:
        import matplotlib.pyplot as plt

        train = {"metadata": {"dataset_split": "train"}, "overall": {"total_trials": 6},
                 "per_skill": {"example": {"tp": 4, "fp": 1, "fn": 0, "decided": 6,
                                          "inconclusive": 0, "precision": 0.8,
                                          "recall": 1.0, "f1": 0.8889}}}
        validation = {"metadata": {"dataset_split": "validation"},
                      "overall": {"total_trials": 5},
                      "per_skill": {"example": {"tp": 3, "fp": 0, "fn": 1, "decided": 5,
                                                "inconclusive": 0, "precision": 1.0,
                                                "recall": 0.75, "f1": 0.8571}}}
        entries = [("train.json", train), ("validation.json", validation)]
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "per-skill.png"
            with mock.patch.object(plt, "close"):
                self.assertTrue(plot_evals.train_validation_per_skill(entries, output))
                train_ax, validation_ax = plt.gcf().axes
                self.assertIn("0.800\n4/5", [text.get_text() for text in train_ax.texts])
                self.assertIn("0.750\n3/4", [text.get_text() for text in validation_ax.texts])
                self.assertIn("FP=1 FN=0", train_ax.get_yticklabels()[0].get_text())
                self.assertIn("FP=0 FN=1", validation_ax.get_yticklabels()[0].get_text())
            plt.close("all")
            self.assertTrue(output.is_file())

    def test_radar_uses_skill_axes_and_leaves_undefined_values_missing(self) -> None:
        import matplotlib.pyplot as plt

        summary = {"per_skill": {
            "skill-a": {"precision": 0.0, "recall": 0.5, "f1": 0.0},
            "skill-b": {"precision": None, "recall": 1.0, "f1": None},
            "skill-c": {"precision": 0.75, "recall": 0.25, "f1": 0.5},
        }}
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "radar.png"
            with mock.patch.dict(os.environ, {"MPLCONFIGDIR": str(Path(temp) / "mpl")}), \
                    mock.patch.object(plt, "close"):
                plot_evals.routing_radar(summary, output, "train")
                axes = plt.gcf().axes
                self.assertEqual(len(axes), 3)
                self.assertEqual([tick.get_text() for tick in axes[1].get_xticklabels()],
                                 ["skill-a", "skill-b", "skill-c"])
                self.assertIn("skill-b (N/A)",
                              [tick.get_text() for tick in axes[0].get_xticklabels()])
                self.assertEqual(list(axes[1].lines[0].get_ydata()), [0.5, 1.0, 0.25, 0.5])
                self.assertTrue(math.isnan(axes[0].lines[0].get_ydata()[1]))
            plt.close("all")
            self.assertTrue(output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))

    def test_radar_renders_empty_state_when_fewer_than_three_skills_exist(self) -> None:
        summary = {"per_skill": {"sample": {"precision": 1.0, "recall": 1.0, "f1": 1.0}}}
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "radar.png"
            with mock.patch.dict(os.environ, {"MPLCONFIGDIR": str(Path(temp) / "mpl")}):
                plot_evals.routing_radar(summary, output, "train")
            self.assertTrue(output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))

    def test_paired_charts_keep_splits_distinct_in_one_file(self) -> None:
        """Check paired charts show both splits, without pooling their observations.

        中文：确认同一张图保留训练/验证的独立计数与图例，不合并样本。
        """
        import matplotlib.pyplot as plt

        def summary(split: str, tp: int) -> dict:
            """Build a minimal split-specific summary for paired chart tests.

            中文：构造带不同真阳性数的两份最小结果。
            """
            return {"metadata": {"dataset_split": split},
                    "overall": {"tp": tp, "fn": 1, "fp": 0, "tn": 2,
                                "inconclusive_positive": 0, "inconclusive_negative": 0},
                    "per_skill": {name: {"precision": 1.0, "recall": rate, "f1": rate}
                                  for name, rate in zip(("a", "b", "c"), (1.0, 0.75, 0.5))}}

        train, validation = summary("train", 8), summary("validation", 3)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with mock.patch.dict(os.environ, {"MPLCONFIGDIR": str(root / "mpl")}), \
                    mock.patch.object(plt, "close"):
                plot_evals.confusion_matrix(train, root / "confusion.png", validation)
                axes = [ax for ax in plt.gcf().axes if ax.images]
                self.assertEqual([ax.get_title() for ax in axes],
                                 ["Train routing", "Validation routing"])
                self.assertEqual([ax.images[0].get_array()[0, 0] for ax in axes], [8, 3])
                self.assertEqual([ax.images[0].norm.vmax for ax in axes], [8, 8])
                plot_evals.routing_radar(train, root / "radar.png", "train", validation)
                self.assertEqual([len(ax.lines) for ax in plt.gcf().axes], [2, 2, 2])
                self.assertEqual([text.get_text() for text in plt.gcf().legends[0].get_texts()],
                                 ["train", "validation"])
            plt.close("all")


if __name__ == "__main__":
    unittest.main()
