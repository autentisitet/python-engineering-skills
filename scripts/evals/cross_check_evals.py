#!/usr/bin/env python3
"""Cross-check routing errors under a caller-supplied model.

Reads a baseline result file, re-runs the cases that were routing errors in it under a
different model (passed with ``--model`` or ``--profile``, never hardcoded), and reports
which errors disappear, which persist, and - with ``--all-cases`` - which new errors appear.
"""
from __future__ import annotations
import argparse
from enum import StrEnum
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

from scripts.evals import run_activation_evals as activation
from scripts.evals.validate_evals import case_sha256, load_cases


class Outcome(StrEnum):
    PASS = "pass"
    ERROR = "error"
    UNDETERMINED = "undetermined"
    UNKNOWN = "unknown"


def trial_outcome(trial: object, should_trigger: bool) -> Outcome:
    """Classify one trial from reliable routing evidence.

    中文：根据可靠的技能读取证据，把单次 trial 归类为通过、错误或无法判定。

    Design / 设计：``match`` 表达互斥状态；已完成的正例漏触发属于错误，基础设施失败保持无法判定，
    避免把缺失证据计入模型质量。
    """
    if not isinstance(trial, dict):
        return Outcome.UNDETERMINED
    match trial.get("status"):
        case "pass":
            return Outcome.PASS
        case "fail":
            return Outcome.ERROR
        case "inconclusive" if (
            should_trigger
            and trial.get("turn_completed") is True
            and not trial.get("infrastructure_failure")
        ):
            return Outcome.ERROR
        case _:
            return Outcome.UNDETERMINED


def case_outcome(row: dict) -> Outcome:
    """Reduce repeated trials to one case outcome.

    中文：聚合同一查询的多次 trial，生成一个稳定的 case 结果。

    Algorithm / 算法：采用保守优先级 ``ERROR > PASS > UNDETERMINED > UNKNOWN``；任一可靠错误都会
    使 case 判错，只有全部有效 trial 通过时才判通过。
    """
    outcomes = {
        trial_outcome(trial, bool(row.get("should_trigger")))
        for trial in row.get("trials", [])
    }
    if not outcomes:
        return Outcome.UNKNOWN
    if Outcome.ERROR in outcomes:
        return Outcome.ERROR
    if outcomes == {Outcome.PASS}:
        return Outcome.PASS
    return Outcome.UNDETERMINED


def baseline_error_ids(result: dict) -> set[str]:
    """Return case ids classified as routing errors.

    中文：返回基线结果中被归类为路由错误的查询 ID 集合。
    """
    return {
        row["id"]
        for row in result.get("results", [])
        if isinstance(row.get("id"), str) and case_outcome(row) is Outcome.ERROR
    }


def baseline_query_mismatches(result: dict, cases: list[dict], dataset_sha256: str) -> list[str]:
    """Find baseline rows that cannot be matched to the current dataset safely.

    中文：找出无法与当前数据集逐条核对的基线查询；旧结果仅在完整 JSON 摘要匹配时可复用。
    """
    current = {case["id"]: case_sha256(case) for case in cases}
    same_dataset = result.get("dataset_sha256") == dataset_sha256
    mismatches = []
    for row in result.get("results", []):
        identifier = row.get("id")
        recorded = row.get("case_sha256")
        if identifier not in current or (
            recorded != current[identifier] and not (recorded is None and same_dataset)
        ):
            mismatches.append(str(identifier))
    return mismatches


def result_rows(result: dict) -> dict[str, dict]:
    """Index result rows by case id.

    中文：按查询 ID 索引评测结果行，便于比较两次运行。
    """
    return {row.get("id"): row for row in result.get("results", [])}


def compare_runs(baseline: dict, new: dict, queries: dict[str, dict]) -> dict:
    """Compare two result payloads and bucket each common case.

    中文：比较基线与新结果，把共有查询分为已解决、持续、未判定和新引入错误。
    """
    baseline_rows = result_rows(baseline)
    new_rows = result_rows(new)
    resolved: list[dict] = []
    persisted: list[dict] = []
    unresolved: list[dict] = []
    introduced: list[dict] = []
    for case_id in sorted(set(baseline_rows) & set(new_rows)):
        base_row = baseline_rows[case_id]
        new_row = new_rows[case_id]
        base_outcome = case_outcome(base_row)
        new_outcome = case_outcome(new_row)
        record = {
            "id": case_id,
            "skill": new_row.get("skill") or base_row.get("skill") or "",
            "query": queries.get(case_id, {}).get("query", ""),
            "baseline": base_outcome.value,
            "new": new_outcome.value,
        }
        if base_outcome is Outcome.ERROR:
            if new_outcome is Outcome.PASS:
                resolved.append(record)
            elif new_outcome is Outcome.ERROR:
                persisted.append(record)
            else:
                unresolved.append(record)
        elif base_outcome is Outcome.PASS and new_outcome is Outcome.ERROR:
            introduced.append(record)
    return {
        "resolved": resolved,
        "persisted": persisted,
        "unresolved": unresolved,
        "introduced": introduced,
    }


def build_subset_dataset(dataset: Path, ids: set[str], output: Path) -> None:
    """Write a dataset containing selected case ids while preserving metadata.

    中文：保留数据集外层元数据，仅写出指定查询 ID 的子数据集。
    """
    data = json.loads(dataset.read_text(encoding="utf-8"))
    queries = [query for query in data.get("queries", []) if query.get("id") in ids]
    subset = dict(data)
    subset["queries"] = queries
    output.write_text(json.dumps(subset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_evals(dataset: Path, output: Path, args: argparse.Namespace) -> int:
    """Invoke the activation runner with forwarded cross-check options.

    中文：转发模型、环境和运行参数，调用现有激活评测入口。

    Design / 设计：复用 activation CLI 的单一参数解析与安全校验，临时替换 ``sys.argv`` 后在
    ``finally`` 中恢复，避免维护第二套 runner 实现。
    """
    argv = [
        "run_activation_evals", str(dataset), "--allow-model-calls",
        "--runs", str(args.runs), "--jobs", str(args.jobs),
        "--timeout", str(args.timeout), "--output", str(output),
    ]
    for flag, value in (
        ("--profile", args.profile),
        ("--model", args.model),
        ("--reasoning-effort", args.reasoning_effort),
    ):
        if value is not None:
            argv.extend((flag, str(value)))
    for value in args.pass_env:
        argv.extend(("--pass-env", value))
    previous = sys.argv
    try:
        sys.argv = argv
        return activation.main()
    finally:
        sys.argv = previous


def print_report(diff: dict, json_out: bool = False) -> None:
    """Print the cross-check comparison as text or JSON.

    中文：以文本或 JSON 形式输出跨模型比较结果。
    """
    if json_out:
        print(json.dumps(diff, ensure_ascii=False, indent=2))
        return
    resolved = diff["resolved"]
    persisted = diff["persisted"]
    unresolved = diff["unresolved"]
    introduced = diff["introduced"]
    print(f"resolved={len(resolved)} persisted={len(persisted)} "
          f"unresolved={len(unresolved)} introduced={len(introduced)}")
    for label, cases in (
        ("resolved", resolved),
        ("persisted", persisted),
        ("unresolved", unresolved),
        ("introduced", introduced),
    ):
        if not cases:
            continue
        print(f"\n[{label}]")
        for record in cases:
            print(f"  {record['id']} ({record['skill']}): {record['baseline']} -> {record['new']}")
            print(f"      {record['query']}")


def main() -> int:
    """Run the cross-model error recheck CLI.

    中文：解析参数、重跑基线错误并报告新旧模型的差异。
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True,
                        help="existing result file whose routing errors should be re-checked")
    parser.add_argument("--dataset", type=Path, required=True,
                        help="source query set used by the baseline run")
    parser.add_argument("--output", type=Path, required=True,
                        help="path for the new model result file")
    parser.add_argument("--model", default=None,
                        help="model passed to every fresh codex exec session (never hardcoded)")
    parser.add_argument("--profile", default=None,
                        help="profile passed through to every fresh codex exec session")
    parser.add_argument("--reasoning-effort", default=None,
                        help="override model_reasoning_effort (e.g. low/medium/high)")
    parser.add_argument("--pass-env", action="append", default=[], metavar="NAME",
                        help="pass one named host variable to Codex; repeatable")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--all-cases", action="store_true",
                        help="run the full dataset instead of only the baseline error cases")
    parser.add_argument("--allow-model-calls", action="store_true",
                        help="confirm that running the cross-check will invoke the model")
    parser.add_argument("--json", action="store_true", dest="json_out",
                        help="print the comparison as JSON")
    args = parser.parse_args()

    if not args.allow_model_calls:
        parser.error("explicit --allow-model-calls is required; this invokes the model")
    if args.model is None and args.profile is None:
        parser.error("--model or --profile is required")
    if args.runs < 1 or not 1 <= args.jobs <= 4:
        parser.error("positive --runs and --jobs 1..4 required")
    if args.timeout < 1:
        parser.error("--timeout must be at least 1 second")

    try:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        parser.error(f"cannot read baseline result: {error}")

    cases, errors = load_cases(args.dataset)
    if errors or not cases:
        parser.error("invalid or empty dataset")
    mismatches = baseline_query_mismatches(
        baseline, cases, hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    )
    if mismatches:
        parser.error("baseline queries changed or lack verifiable hashes: "
                     + ", ".join(mismatches[:5])
                     + "; rerun the baseline with the current dataset")
    queries = {case["id"]: case for case in cases}

    error_ids = baseline_error_ids(baseline)
    if args.all_cases:
        run_dataset = args.dataset
        print(f"cross-checking all {len(cases)} cases under {args.model or args.profile}",
              file=sys.stderr)
    else:
        if not error_ids:
            print("no baseline errors to cross-check", file=sys.stderr)
            return 0
        run_dataset = Path(tempfile.mkdtemp(prefix="cross-check-")) / "cases.json"
        build_subset_dataset(args.dataset, error_ids, run_dataset)
        print(f"cross-checking {len(error_ids)} baseline error case(s) under "
              f"{args.model or args.profile}", file=sys.stderr)

    try:
        code = run_evals(run_dataset, args.output, args)
    finally:
        if not args.all_cases:
            shutil.rmtree(run_dataset.parent, ignore_errors=True)
    if code == 2:
        return 2

    try:
        new = json.loads(args.output.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        parser.error(f"cannot read new result: {error}")

    diff = compare_runs(baseline, new, queries)
    print_report(diff, args.json_out)
    return 0 if not (diff["persisted"] or diff["unresolved"] or diff["introduced"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
