#!/usr/bin/env python3
"""Validate stable train/validation routing datasets for every skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVALS_DIR = ROOT / "evals"
SPLITS = ("train_queries.json", "validation_queries.json")
CATEGORIES = ("direct", "indirect", "embedded", "boundary")
POSITIVE_CATEGORIES = ("direct", "indirect", "embedded")
CASE_KEYS = {"id", "skill", "category", "query", "should_trigger"}
ID_RANGES = {
    ("train_queries.json", True): range(1, 8),
    ("train_queries.json", False): range(1, 7),
    ("validation_queries.json", True): range(8, 13),
    ("validation_queries.json", False): range(7, 11),
}


def case_sha256(case: dict) -> str:
    """Hash the identity, label, and request text used by one activation trial.

    中文：对单条试验依赖的 ID、技能、类别、标签和查询文本计算稳定摘要。
    """
    canonical = json.dumps(
        {key: case[key] for key in ("id", "skill", "category", "query", "should_trigger")},
        sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_cases(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Load and structurally validate cases from one dataset file.

    中文：读取单个数据集文件并校验每条查询的字段、类型、类别与标签关系。
    """
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return [], [f"{path}: cannot read JSON: {error}"]
    if not isinstance(value, dict):
        return [], [f"{path}: top-level value must be an object with a `queries` array"]
    queries = value.get("queries")
    if not isinstance(queries, list):
        return [], [f"{path}: `queries` must be an array"]
    errors: list[str] = []
    cases: list[dict[str, Any]] = []
    for index, case in enumerate(queries):
        location = f"{path}.queries[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{location}: case must be an object")
            continue
        if set(case) != CASE_KEYS:
            errors.append(
                f"{location}: fields must be id, skill, category, query, and should_trigger"
            )
            continue
        if not all(isinstance(case[key], str) and case[key].strip() for key in ("id", "skill", "category", "query")):
            errors.append(f"{location}: id, skill, category, and query must be non-empty strings")
            continue
        if not isinstance(case["should_trigger"], bool):
            errors.append(f"{location}: should_trigger must be boolean")
            continue
        if case["category"] not in CATEGORIES:
            errors.append(
                f"{location}: category must be one of {', '.join(CATEGORIES)}"
            )
            continue
        if case["should_trigger"] and case["category"] not in POSITIVE_CATEGORIES:
            errors.append(
                f"{location}: positive category must be one of {', '.join(POSITIVE_CATEGORIES)}"
            )
            continue
        if not case["should_trigger"] and case["category"] != "boundary":
            errors.append(f"{location}: negative category must be boundary")
            continue
        cases.append(case)
    return cases, errors


def validate_wrapper(path: Path, expected_split: str) -> list[str]:
    """Validate dataset envelope metadata independently of query contents.

    中文：独立校验数据集版本、split 和 split seed 等外层元数据。
    """
    errors: list[str] = []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return [f"{path}: cannot read JSON: {error}"]
    if not isinstance(value, dict):
        return [f"{path}: top-level value must be an object"]
    if value.get("version") != 1:
        errors.append(f"{path}: version must be 1")
    if value.get("split") != expected_split:
        errors.append(f"{path}: split must be {expected_split!r}")
    if not isinstance(value.get("split_seed"), int):
        errors.append(f"{path}: split_seed must be an integer")
    return errors


def validate(evals_dir: Path, skills_dir: Path) -> list[str]:
    """Validate both fixed splits against the registered repository skills.

    中文：校验固定训练/验证划分的数量、ID、重复项与技能注册完整性。

    Design / 设计：使用固定 ID 区间和精确计数锁定 split，防止查询在人工编辑 JSON/CSV 后静默跨集
    漂移或重复。
    """
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
        expected_split = "train" if filename == "train_queries.json" else "validation"
        errors.extend(validate_wrapper(path, expected_split))
        cases, load_errors = load_cases(path)
        errors.extend(load_errors)
        all_cases.extend(cases)

        counts: dict[str, Counter[bool]] = defaultdict(Counter)
        numbers: dict[tuple[str, bool], list[int]] = defaultdict(list)
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
            valid_numbers = ID_RANGES[(filename, case["should_trigger"])]
            if number not in valid_numbers:
                errors.append(f"{path}: case id belongs to the wrong split: {case['id']}")
        for skill in sorted(expected_skills):
            for should_trigger, label in ((True, "positive"), (False, "negative")):
                valid_numbers = ID_RANGES[(filename, should_trigger)]
                expected_count = len(valid_numbers)
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
    """Parse dataset-validation CLI arguments.

    中文：解析数据集校验命令的目录参数。
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evals-dir", type=Path, default=DEFAULT_EVALS_DIR)
    parser.add_argument("--skills-dir", type=Path, default=ROOT / "skills")
    return parser.parse_args()


def main() -> int:
    """Run dataset validation and return a process exit code.

    中文：执行完整数据集校验，打印诊断并返回标准退出码。
    """
    args = parse_args()
    errors = validate(args.evals_dir.resolve(), args.skills_dir.resolve())
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Validated fixed train/validation routing datasets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
