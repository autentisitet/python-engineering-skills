#!/usr/bin/env python3
"""Validate stable train/validation routing datasets for every skill."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVALS_DIR = ROOT / "evals"
SPLITS = ("train_queries.json", "validation_queries.json")


def load_cases(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return [], [f"{path}: cannot read JSON array: {error}"]
    if not isinstance(value, list):
        return [], [f"{path}: top-level value must be an array"]
    errors: list[str] = []
    cases: list[dict[str, Any]] = []
    for index, case in enumerate(value):
        location = f"{path}[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{location}: case must be an object")
            continue
        if set(case) != {"id", "query", "should_trigger", "skill"}:
            errors.append(f"{location}: fields must be id, query, should_trigger, and skill")
            continue
        if not all(isinstance(case[key], str) and case[key].strip() for key in ("id", "query", "skill")):
            errors.append(f"{location}: id, query, and skill must be non-empty strings")
            continue
        if not isinstance(case["should_trigger"], bool):
            errors.append(f"{location}: should_trigger must be boolean")
            continue
        cases.append(case)
    return cases, errors


def validate(evals_dir: Path, skills_dir: Path) -> list[str]:
    errors: list[str] = []
    if not skills_dir.is_dir():
        return [f"skills directory does not exist: {skills_dir}"]
    if not evals_dir.is_dir():
        return [f"evals directory does not exist: {evals_dir}"]
    expected_skills = {
        path.name for path in skills_dir.iterdir() if path.is_dir() and (path / "SKILL.md").is_file()
    }
    all_cases: list[dict[str, Any]] = []
    for filename in SPLITS:
        path = evals_dir / filename
        cases, load_errors = load_cases(path)
        errors.extend(load_errors)
        all_cases.extend(cases)

        counts: dict[str, Counter[bool]] = defaultdict(Counter)
        numbers: dict[tuple[str, bool], list[int]] = defaultdict(list)
        valid_numbers = range(1, 7) if filename == "train_queries.json" else range(7, 11)
        for case in cases:
            counts[case["skill"]][case["should_trigger"]] += 1
            expected_label = "positive" if case["should_trigger"] else "negative"
            prefix = f"{case['skill']}-{expected_label}-"
            suffix = case["id"][len(prefix):] if case["id"].startswith(prefix) else ""
            if len(suffix) != 2 or not suffix.isdigit():
                errors.append(f"{path}: malformed case id: {case['id']}")
                continue
            number = int(suffix)
            numbers[(case["skill"], case["should_trigger"])].append(number)
            if number not in valid_numbers:
                errors.append(f"{path}: case id belongs to the wrong split: {case['id']}")
        for skill in sorted(expected_skills):
            expected_count = len(valid_numbers)
            for should_trigger, label in ((True, "positive"), (False, "negative")):
                actual_numbers = numbers[(skill, should_trigger)]
                if counts[skill][should_trigger] != expected_count:
                    errors.append(
                        f"{path}: {skill} must have exactly {expected_count} {label} cases"
                    )
                if sorted(actual_numbers) != list(valid_numbers):
                    errors.append(
                        f"{path}: {skill} {label} ids must use each number "
                        f"{min(valid_numbers):02d}-{max(valid_numbers):02d} exactly once"
                    )

    ids = Counter(case["id"] for case in all_cases)
    queries = Counter(case["query"].casefold().strip() for case in all_cases)
    for identifier, count in ids.items():
        if count > 1:
            errors.append(f"duplicate case id: {identifier}")
    for query, count in queries.items():
        if count > 1:
            errors.append(f"duplicate query across eval datasets: {query!r}")

    actual_skills = {case["skill"] for case in all_cases}
    unknown = actual_skills - expected_skills
    missing = expected_skills - actual_skills
    if unknown:
        errors.append("unknown skills in evals: " + ", ".join(sorted(unknown)))
    if missing:
        errors.append("skills without evals: " + ", ".join(sorted(missing)))

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evals-dir", type=Path, default=DEFAULT_EVALS_DIR)
    parser.add_argument("--skills-dir", type=Path, default=ROOT / "skills")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors = validate(args.evals_dir.resolve(), args.skills_dir.resolve())
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Validated fixed train/validation routing datasets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
