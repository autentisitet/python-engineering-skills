#!/usr/bin/env python3
"""Build a retry dataset from inconclusive cases in an activation result file."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def read_json(path: Path) -> dict:
    """Read one JSON object or raise a user-facing value error.

    中文：读取单个 JSON 对象，并把文件或格式错误转换为可读异常。
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {path}: {error}") from error


def extract_cases(result: dict, source: dict, reason: str | None) -> tuple[list[dict], list[str]]:
    """Select source cases with an inconclusive trial matching ``reason``.

    中文：筛选包含指定不可判定原因的源查询，并返回结果中缺失的查询 ID。
    """
    source_queries = [query for query in source.get("queries", []) if isinstance(query, dict)]
    by_id = {query.get("id"): query for query in source_queries if isinstance(query.get("id"), str)}
    selected_ids: set[str] = set()
    missing_ids: list[str] = []
    for row in result.get("results", []):
        row_id = row.get("id")
        if row_id not in by_id:
            missing_ids.append(str(row_id))
            continue
        for trial in row.get("trials", []):
            if trial.get("status") != "inconclusive":
                continue
            if reason is None or trial.get("reason") == reason:
                selected_ids.add(row_id)
                break
    selected = [query for query in source_queries if query.get("id") in selected_ids]
    return selected, missing_ids


def main() -> int:
    """Build and write a retry dataset from activation results.

    中文：从激活评测结果中提取需要重试的查询并写入新数据集。
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reason", default="timeout",
                        help="retry only inconclusive trials with this reason (default: timeout)")
    parser.add_argument("--any-inconclusive", action="store_true",
                        help="retry every inconclusive trial regardless of reason")
    args = parser.parse_args()

    try:
        result = read_json(args.result)
        source = read_json(args.dataset)
        reason = None if args.any_inconclusive else args.reason
        selected, missing_ids = extract_cases(result, source, reason)
        payload = {
            "version": source.get("version", 1),
            "split": source.get("split"),
            "split_seed": source.get("split_seed"),
            "queries": selected,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except (ValueError, OSError, UnicodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if missing_ids:
        print(f"warning: result ids not found in dataset: {missing_ids}", file=sys.stderr)
    print(f"wrote {args.output} ({len(selected)} retry cases)")
    return 0 if selected else 1


if __name__ == "__main__":
    raise SystemExit(main())
