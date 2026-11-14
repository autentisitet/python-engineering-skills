#!/usr/bin/env python3
"""Summarize activation eval results into routing metrics (standard library only)."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from scripts.evals.validate_evals import case_sha256, load_cases

ROOT = Path(__file__).resolve().parents[2]
INCONCLUSIVE_REASONS = {
    "timeout": "timeout",
    "agent_process_failed": "process_failed",
    "completion_event_missing": "completion_missing",
    "evaluation_unavailable": "unavailable",
}


def classify(trial: dict, should_trigger: bool) -> str:
    """Map one trial to a confusion-matrix or inconclusive bucket.

    The harness reports three statuses: ``pass``, ``fail``, and ``inconclusive``.
    ``inconclusive`` is split into infrastructure failures (no reliable evidence)
    and routing misses (a positive case whose turn completed without reading the
    skill, which is a false negative rather than missing evidence).

    中文：把单次 trial 映射到 TP/FN/FP/TN 或正负例不可判定桶，并区分路由错误与基础设施失败。
    """
    status = trial.get("status")
    if status == "pass":
        return "tp" if should_trigger else "tn"
    if status == "fail":
        return "fp" if not should_trigger else "fn"
    if trial.get("infrastructure_failure"):
        return "inc_pos" if should_trigger else "inc_neg"
    return "fn" if should_trigger else "inc_neg"


def ratio(numerator: int, denominator: int) -> float | None:
    """Return a rounded ratio or None for an empty denominator.

    中文：计算四位小数比率；分母为零时返回 ``None``。
    """
    return round(numerator / denominator, 4) if denominator else None


def percentile(values: list[float], probability: float) -> float | None:
    """Return a linearly interpolated percentile.

    中文：使用线性插值计算指定分位数，空输入返回 ``None``。

    Algorithm / 算法：采用排序后相邻样本线性插值，与常见统计工具的连续分位数定义一致，避免小样本
    直接取整造成阶跃偏差。
    """
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 3)


def metrics(tp: int, fn: int, fp: int, tn: int) -> dict:
    """Compute routing metrics from decided confusion-matrix counts.

    中文：根据 TP、FN、FP、TN 计算 precision、recall、specificity、F1 等指标。

    Statistics / 统计：只使用有可靠证据的 decided trials；基础设施不可判定样本由 coverage 单独反映，
    不进入分类指标分母。
    """
    decided = tp + fn + fp + tn
    precision = ratio(tp, tp + fp)
    recall = ratio(tp, tp + fn)
    specificity = ratio(tn, tn + fp)
    if precision is None or recall is None:
        f1 = None
    elif precision + recall == 0:
        f1 = 0.0
    else:
        f1 = round(2 * precision * recall / (precision + recall), 4)
    balanced_accuracy = (
        round((recall + specificity) / 2, 4)
        if recall is not None and specificity is not None else None
    )
    return {
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
        "decided": decided,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "false_positive_rate": ratio(fp, fp + tn),
        "false_negative_rate": ratio(fn, fn + tp),
        "accuracy": ratio(tp + tn, decided),
        "balanced_accuracy": balanced_accuracy,
        "f1": f1,
    }


def trial_loaded(trial: dict, should_trigger: bool) -> bool | None:
    """Return observed activation or None when no reliable evidence exists.

    中文：返回 trial 是否读取目标技能；基础设施失败没有可靠证据时返回 ``None``。
    """
    if trial.get("infrastructure_failure"):
        return None
    observed = trial.get("observed_skill_read")
    if isinstance(observed, bool):
        return observed
    if trial.get("status") == "pass":
        return should_trigger
    if trial.get("status") == "fail":
        return not should_trigger
    return False


def summarize_query(row: dict) -> dict:
    """Summarize trigger rate and coverage for one repeated query.

    中文：汇总单条查询的有效 trial、触发率和覆盖率，不把基础设施失败放入触发率分母。

    Statistics / 统计：trigger rate 衡量重复运行稳定性而非连续置信分数，因此不能用于构造 ROC 或 PR
    曲线。
    """
    trials = row.get("trials", [])
    should_trigger = bool(row.get("should_trigger"))
    observations = [trial_loaded(trial, should_trigger) for trial in trials]
    valid = [loaded for loaded in observations if loaded is not None]
    loaded = sum(valid)
    total = len(trials)
    return {
        "id": row.get("id"),
        "skill": row.get("skill"),
        "category": row.get("category", "unknown"),
        "should_trigger": should_trigger,
        "loaded_trials": loaded,
        "valid_trials": len(valid),
        "inconclusive_trials": total - len(valid),
        "total_trials": total,
        "trigger_rate": ratio(loaded, len(valid)),
        "coverage": ratio(len(valid), total),
    }


def inconclusive_reasons(result: dict) -> dict[str, int]:
    """Count infrastructure failures by stable report label.

    中文：按稳定标签统计超时、进程失败、缺失完成事件等基础设施原因。
    """
    counts: dict[str, int] = {}
    for row in result.get("results", []):
        for trial in row.get("trials", []):
            if not trial.get("infrastructure_failure"):
                continue
            reason = INCONCLUSIVE_REASONS.get(trial.get("reason"), "other")
            counts[reason] = counts.get(reason, 0) + 1
    return counts


def skills_digest(root: Path = ROOT) -> str:
    """Return a digest of the current repository skill packages.

    中文：计算当前仓库全部技能包内容的稳定摘要，用于结果 freshness 检查。

    Algorithm / 算法：按相对路径排序后同时哈希路径和内容，既检测内容变化，也检测文件移动或重命名。
    """
    digest = hashlib.sha256()
    for path in sorted((root / "skills").rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


def result_freshness(result: dict) -> dict:
    """Compare recorded skill and dataset digests with the current tree.

    中文：比较结果记录的摘要与当前仓库，标记技能和数据集是否仍为最新。

    Design / 设计：完整数据集使用 JSON 文件 SHA；子集使用逐条查询 SHA 比较当前数据集。
    缺少可比元数据时返回 ``None``，不把未知误报为过期。
    """
    split = result.get("dataset_split")
    dataset = ROOT / "evals" / f"{split}_queries.json" if split in {"train", "validation"} else None
    recorded_dataset_sha = result.get("dataset_sha256")
    recorded_skills_sha = result.get("skills_sha256")
    dataset_current = None
    if dataset is not None and dataset.is_file() and isinstance(recorded_dataset_sha, str):
        if recorded_dataset_sha == hashlib.sha256(dataset.read_bytes()).hexdigest():
            dataset_current = True
        else:
            cases, errors = load_cases(dataset)
            current_cases = {case["id"]: case_sha256(case) for case in cases} if not errors else {}
            rows = result.get("results", [])
            if rows and all(isinstance(row, dict) and isinstance(row.get("case_sha256"), str)
                            and row.get("id") in current_cases for row in rows):
                dataset_current = all(
                    row["case_sha256"] == current_cases[row["id"]] for row in rows
                )
    return {
        "skills_current": (recorded_skills_sha == skills_digest()
                           if isinstance(recorded_skills_sha, str) else None),
        "dataset_current": dataset_current,
    }


def compute_summary(result: dict) -> dict:
    """Aggregate an activation payload into routing, time, and token metrics.

    中文：把激活结果汇总为总体、技能、类别和查询级的路由、耗时与 token 指标。

    Performance / 性能：单次遍历 trial 同时累计所有分组和资源指标，避免为每种报表重复扫描结果文件。
    """
    counts = {"tp": 0, "fn": 0, "fp": 0, "tn": 0, "inc_pos": 0, "inc_neg": 0}
    per_skill: dict[str, dict] = {}
    per_category: dict[str, dict] = {}
    query_summaries: list[dict] = []
    durations: list[float] = []
    skill_durations: dict[str, list[float]] = {}
    token_totals = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
    token_duration_sum = 0.0
    skill_token_totals: dict[str, dict] = {}
    skill_token_duration: dict[str, float] = {}
    usage_trial_count = 0
    for row in result.get("results", []):
        skill = row["skill"]
        should = bool(row["should_trigger"])
        category = row.get("category", "unknown")
        query_summaries.append(summarize_query(row))
        skill_counts = per_skill.setdefault(
            skill, {"tp": 0, "fn": 0, "fp": 0, "tn": 0, "inc_pos": 0, "inc_neg": 0}
        )
        category_counts = per_category.setdefault(
            category, {"tp": 0, "fn": 0, "fp": 0, "tn": 0, "inc_pos": 0, "inc_neg": 0}
        )
        for trial in row["trials"]:
            key = classify(trial, should)
            counts[key] += 1
            skill_counts[key] += 1
            category_counts[key] += 1
            duration = trial.get("duration_seconds")
            if isinstance(duration, (int, float)) and duration >= 0:
                durations.append(float(duration))
                skill_durations.setdefault(skill, []).append(float(duration))
            usage = trial.get("usage") or {}
            input_tokens = usage.get("input_tokens")
            output_tokens = usage.get("output_tokens")
            cached_tokens = usage.get("cached_input_tokens")
            if isinstance(input_tokens, int) and input_tokens >= 0 and isinstance(output_tokens, int) and output_tokens >= 0:
                usage_trial_count += 1
                token_totals["input_tokens"] += input_tokens
                token_totals["output_tokens"] += output_tokens
                token_totals["cached_input_tokens"] += cached_tokens if isinstance(cached_tokens, int) and cached_tokens >= 0 else 0
                if isinstance(duration, (int, float)) and duration >= 0:
                    token_duration_sum += float(duration)
                    skill_token_duration[skill] = skill_token_duration.get(skill, 0.0) + float(duration)
                skill_tokens = skill_token_totals.setdefault(
                    skill, {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
                )
                skill_tokens["input_tokens"] += input_tokens
                skill_tokens["output_tokens"] += output_tokens
                skill_tokens["cached_input_tokens"] += cached_tokens if isinstance(cached_tokens, int) and cached_tokens >= 0 else 0

    total = sum(counts.values())
    inc_total = counts["inc_pos"] + counts["inc_neg"]
    summary = metrics(counts["tp"], counts["fn"], counts["fp"], counts["tn"])
    summary.update({
        "inconclusive_positive": counts["inc_pos"],
        "inconclusive_negative": counts["inc_neg"],
        "inconclusive_total": inc_total,
        "total_trials": total,
        "inconclusive_rate": round(inc_total / total, 4) if total else None,
        "coverage": ratio(summary["decided"], total),
        "duration_seconds_mean": round(sum(durations) / len(durations), 3) if durations else None,
        "duration_seconds_total": round(sum(durations), 3) if durations else None,
        "duration_seconds_min": round(min(durations), 3) if durations else None,
        "duration_seconds_max": round(max(durations), 3) if durations else None,
        "duration_seconds_p50": percentile(durations, 0.5),
        "duration_seconds_p95": percentile(durations, 0.95),
        "session_count": len(durations),
        "input_tokens_total": token_totals["input_tokens"],
        "cached_input_tokens_total": token_totals["cached_input_tokens"],
        "output_tokens_total": token_totals["output_tokens"],
        "total_tokens": token_totals["input_tokens"] + token_totals["output_tokens"],
        "tokens_per_second": round(
            (token_totals["input_tokens"] + token_totals["output_tokens"]) / token_duration_sum, 3
        ) if token_duration_sum else None,
        "usage_trial_count": usage_trial_count,
    })
    skill_summaries = {}
    for skill, values in sorted(per_skill.items()):
        entry = metrics(values["tp"], values["fn"], values["fp"], values["tn"])
        entry["inconclusive"] = values["inc_pos"] + values["inc_neg"]
        skill_total = entry["decided"] + entry["inconclusive"]
        entry["coverage"] = ratio(entry["decided"], skill_total)
        skill_times = skill_durations.get(skill, [])
        entry["duration_seconds_mean"] = round(sum(skill_times) / len(skill_times), 3) if skill_times else None
        entry["duration_seconds_p95"] = percentile(skill_times, 0.95)
        entry["session_count"] = len(skill_times)
        skill_tokens = skill_token_totals.get(skill, {})
        entry["input_tokens_total"] = skill_tokens.get("input_tokens", 0)
        entry["output_tokens_total"] = skill_tokens.get("output_tokens", 0)
        entry["total_tokens"] = entry["input_tokens_total"] + entry["output_tokens_total"]
        skill_duration_sum = skill_token_duration.get(skill, 0.0)
        entry["tokens_per_second"] = round(entry["total_tokens"] / skill_duration_sum, 3) if skill_duration_sum else None
        skill_summaries[skill] = entry
    category_summaries = {}
    for category, values in sorted(per_category.items()):
        entry = metrics(values["tp"], values["fn"], values["fp"], values["tn"])
        entry["inconclusive"] = values["inc_pos"] + values["inc_neg"]
        category_total = entry["decided"] + entry["inconclusive"]
        entry["coverage"] = ratio(entry["decided"], category_total)
        category_summaries[category] = entry
    options = result.get("codex_options")
    options_sha256 = (
        hashlib.sha256(json.dumps(options, sort_keys=True).encode("utf-8")).hexdigest()
        if isinstance(options, dict) else None
    )
    return {
        "metadata": {
            "dataset_version": result.get("dataset_version"),
            "dataset_split": result.get("dataset_split"),
            "dataset_split_seed": result.get("dataset_split_seed"),
            "dataset_sha256": result.get("dataset_sha256"),
            "skills_sha256": result.get("skills_sha256"),
            "codex_version": result.get("codex_version"),
            "codex_options_sha256": options_sha256,
        },
        "overall": summary,
        "per_skill": skill_summaries,
        "per_category": category_summaries,
        "per_query": query_summaries,
        "inconclusive_reasons": inconclusive_reasons(result),
    }


def train_validation_gap(summaries: list[dict]) -> dict | None:
    """Return train-minus-validation metric gaps when both splits exist.

    中文：同时存在训练和验证汇总时，计算训练指标减验证指标的差值。
    """
    by_split = {
        summary.get("metadata", {}).get("dataset_split"): summary
        for summary in summaries
    }
    if "train" not in by_split or "validation" not in by_split:
        return None
    train = by_split["train"]["overall"]
    validation = by_split["validation"]["overall"]
    keys = ("precision", "recall", "specificity", "f1", "accuracy", "balanced_accuracy", "coverage")
    return {
        f"{key}_gap": round(train[key] - validation[key], 4)
        if train.get(key) is not None and validation.get(key) is not None else None
        for key in keys
    }


def format_text(file_path: Path, summary: dict, freshness: dict) -> str:
    """Format one summary as a compact human-readable report.

    中文：把单个结果汇总格式化为便于终端审查的紧凑文本报告。
    """
    overall = summary["overall"]
    lines = [f"=== {file_path} ==="]
    lines.append(
        f"freshness: skills={'current' if freshness['skills_current'] else 'stale'} "
        f"dataset={('current' if freshness['dataset_current'] else 'stale') if freshness['dataset_current'] is not None else 'unknown'}"
    )
    lines.append(
        f"decided={overall['decided']} inconclusive={overall['inconclusive_total']} "
        f"total={overall['total_trials']}"
    )
    if summary["inconclusive_reasons"]:
        lines.append(
            "inconclusive_reasons="
            + ",".join(f"{reason}:{count}" for reason, count in sorted(summary["inconclusive_reasons"].items()))
        )
    lines.append(
        f"TP={overall['tp']} FN={overall['fn']} FP={overall['fp']} TN={overall['tn']}"
    )
    lines.append(
        f"precision={overall['precision']} recall={overall['recall']} "
        f"specificity={overall['specificity']} f1={overall['f1']} "
        f"accuracy={overall['accuracy']} balanced_accuracy={overall['balanced_accuracy']}"
    )
    lines.append(
        f"FPR={overall['false_positive_rate']} FNR={overall['false_negative_rate']} "
        f"inconclusive_rate={overall['inconclusive_rate']} coverage={overall['coverage']}"
    )
    lines.append(
        f"duration_seconds_mean={overall['duration_seconds_mean']} "
        f"total={overall['duration_seconds_total']} "
        f"min={overall['duration_seconds_min']} max={overall['duration_seconds_max']} "
        f"p50={overall['duration_seconds_p50']} p95={overall['duration_seconds_p95']} "
        f"sessions={overall['session_count']}"
    )
    lines.append(
        f"input_tokens_total={overall['input_tokens_total']} "
        f"cached_input_tokens_total={overall['cached_input_tokens_total']} "
        f"output_tokens_total={overall['output_tokens_total']} "
        f"total_tokens={overall['total_tokens']} "
        f"tokens_per_second={overall['tokens_per_second']} "
        f"usage_trials={overall['usage_trial_count']}"
    )
    for skill, entry in summary["per_skill"].items():
        lines.append(
            f"  {skill:28s} P={entry['precision']} R={entry['recall']} "
            f"S={entry['specificity']} F1={entry['f1']} coverage={entry['coverage']} "
            f"inc={entry['inconclusive']} "
            f"avg_duration_seconds={entry['duration_seconds_mean']} "
            f"total_tokens={entry['total_tokens']} tokens_per_second={entry['tokens_per_second']}"
        )
    return "\n".join(lines)


def main() -> int:
    """Run the result summarization CLI.

    中文：读取一个或多个激活结果，输出文本或 JSON 汇总并按需写入文件。
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path, help="activation result JSON files")
    parser.add_argument("--json", action="store_true", help="emit one JSON array to stdout")
    parser.add_argument("--output", type=Path, help="write the JSON summaries to this file")
    args = parser.parse_args()

    payloads = []
    for path in args.files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            print(f"{path}: cannot read result JSON: {exc}", file=sys.stderr)
            return 2
        payloads.append({
            "file": str(path),
            "freshness": result_freshness(data),
            "summary": compute_summary(data),
        })

    if args.json:
        text = json.dumps(payloads, ensure_ascii=False, indent=2) + "\n"
    else:
        text = "\n\n".join(
            format_text(Path(entry["file"]), entry["summary"], entry["freshness"])
            for entry in payloads
        )
        gap = train_validation_gap([entry["summary"] for entry in payloads])
        if gap is not None:
            text += "\n\n=== train - validation gaps ===\n"
            text += " ".join(f"{key}={value}" for key, value in gap.items())
        text += "\n"

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payloads, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
