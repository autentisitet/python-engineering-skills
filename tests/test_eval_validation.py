#!/usr/bin/env python3
"""Regression tests for fixed routing-evaluation datasets."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.evals import validate_evals


ROOT = Path(__file__).resolve().parents[1]


class EvalValidationTests(unittest.TestCase):
    @staticmethod
    def write_dataset(root: Path, skills: tuple[str, ...] = ("sample-skill",)) -> tuple[Path, Path]:
        skills_dir = root / "skills"
        evals_dir = root / "evals"
        skills_dir.mkdir()
        evals_dir.mkdir()
        for skill in skills:
            package = skills_dir / skill
            package.mkdir()
            (package / "SKILL.md").write_text(
                f"---\nname: {skill}\ndescription: Test routing.\n---\n# Sample\n",
                encoding="utf-8",
            )
        for filename, positive_numbers, negative_numbers in (
            ("train_queries.json", range(1, 8), range(1, 7)),
            ("validation_queries.json", range(8, 13), range(7, 11)),
        ):
            cases = []
            for skill in skills:
                cases.extend({
                    "id": f"{skill}-positive-{number:02d}",
                    "skill": skill,
                    "category": "direct",
                    "query": f"{filename} {skill} positive {number}",
                    "should_trigger": True,
                } for number in positive_numbers)
                cases.extend({
                    "id": f"{skill}-negative-{number:02d}",
                    "skill": skill,
                    "category": "boundary",
                    "query": f"{filename} {skill} negative {number}",
                    "should_trigger": False,
                } for number in negative_numbers)
            payload = {
                "version": 1,
                "split": "train" if filename == "train_queries.json" else "validation",
                "split_seed": 20261112,
                "queries": cases,
            }
            (evals_dir / filename).write_text(json.dumps(payload), encoding="utf-8")
        return evals_dir, skills_dir

    def test_repository_splits(self) -> None:
        self.assertEqual(validate_evals.validate(ROOT / "evals", ROOT / "skills"), [])

    def test_bad_labels_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "cases.json"
            path.write_text(json.dumps({
                "version": 1,
                "split": "train",
                "split_seed": 20261112,
                "queries": [{
                    "id": "x", "skill": "s", "category": "direct",
                    "query": "q", "should_trigger": "false",
                }],
            }))
            _, errors = validate_evals.load_cases(path)
            self.assertTrue(errors)

    def test_case_id_must_match_label_and_split(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            evals, skills = self.write_dataset(Path(temp))
            train_path = evals / "train_queries.json"
            payload = json.loads(train_path.read_text())
            payload["queries"][0]["id"] = "sample-skill-positive-08"
            train_path.write_text(json.dumps(payload), encoding="utf-8")
            errors = validate_evals.validate(evals, skills)
            self.assertTrue(any("wrong split" in error for error in errors))

    def test_missing_duplicate_unknown_and_missing_skill_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            evals, skills = self.write_dataset(Path(temp), ("sample-skill", "unused-skill"))
            train_path = evals / "train_queries.json"
            payload = json.loads(train_path.read_text())
            payload["queries"] = [
                case for case in payload["queries"] if case["skill"] != "unused-skill"
            ]
            payload["queries"][1]["id"] = payload["queries"][0]["id"]
            payload["queries"].append({
                "id": "unknown-skill-positive-01",
                "skill": "unknown-skill",
                "category": "direct",
                "query": "Unknown skill query",
                "should_trigger": True,
            })
            train_path.write_text(json.dumps(payload), encoding="utf-8")
            validation_path = evals / "validation_queries.json"
            validation_payload = json.loads(validation_path.read_text())
            validation_payload["queries"] = [
                case for case in validation_payload["queries"]
                if case["skill"] != "unused-skill"
            ]
            validation_path.write_text(json.dumps(validation_payload), encoding="utf-8")

            errors = validate_evals.validate(evals, skills)
            self.assertTrue(any("duplicate case id" in error for error in errors))
            self.assertTrue(any("unknown skills" in error for error in errors))
            self.assertTrue(any("skills without evals" in error for error in errors))
            self.assertTrue(any("exactly once" in error for error in errors))

    def test_missing_directories_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertTrue(validate_evals.validate(root / "missing-evals", root / "missing-skills"))


if __name__ == "__main__":
    unittest.main()
