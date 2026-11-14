#!/usr/bin/env python3
"""Render activation eval summaries as charts (requires matplotlib).

Matplotlib is imported lazily so the script fails cleanly with a message when it
is not installed, and the repository's offline validation never needs it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

from scripts.evals.summarize_evals import compute_summary

ROOT = Path(__file__).resolve().parents[2]


def split_name(summary: dict) -> str | None:
    """Identify a split from metadata or a matching canonical dataset digest.

    中文：优先使用显式 split；旧结果只在 JSON 摘要精确匹配时识别训练集或验证集。
    """
    metadata = summary["metadata"]
    if metadata.get("dataset_split") in ("train", "validation"):
        return metadata["dataset_split"]
    digest = metadata.get("dataset_sha256")
    if not isinstance(digest, str):
        return None
    for split in ("train", "validation"):
        path = ROOT / "evals" / f"{split}_queries.json"
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == digest:
            return split
    return None


def paired_splits(entries: list[tuple[str, dict]]) -> dict[str, dict] | None:
    """Select exactly one comparable train and validation result.

    中文：只比较各一份训练/验证结果；已记录的技能、模型选项或 CLI 版本不同则拒绝配对。
    """
    if len(entries) != 2:
        return None
    by_split = {split_name(summary): summary for _, summary in entries}
    if set(by_split) != {"train", "validation"}:
        return None
    train = by_split["train"]["metadata"]
    validation = by_split["validation"]["metadata"]
    for key in ("skills_sha256", "codex_options_sha256", "codex_version"):
        if train.get(key) is not None and validation.get(key) is not None:
            if train[key] != validation[key]:
                return None
    return by_split


def comparable_iterations(entries: list[tuple[str, dict]]) -> bool:
    """Require recorded, matching dataset and runtime conditions for a trend.

    中文：只有同一 split、数据集摘要、Codex 版本和运行选项均已记录且一致时才绘制迭代趋势。
    """
    if len(entries) < 2:
        return False
    split = split_name(entries[0][1])
    if split is None or any(split_name(summary) != split for _, summary in entries):
        return False
    for key in ("dataset_sha256", "codex_version", "codex_options_sha256"):
        values = [summary["metadata"].get(key) for _, summary in entries]
        if any(value is None for value in values) or len(set(values)) != 1:
            return False
    return True


def plotted_value(value: float | None) -> float:
    """Keep undefined rates missing rather than drawing them at zero.

    中文：用 NaN 在 Matplotlib 中保留空值，使未定义指标不会被误绘为零。
    """
    return math.nan if value is None else value


def annotate_bars(ax, bars, values: list[float | None], format_spec: str = ".3f",
                  show_values: bool = True) -> None:
    """Label bars with measured values or an explicit N/A marker.

    中文：已定义数值显示真实大小，分母为零时在基线位置明确标记 N/A。
    """
    for bar, value in zip(bars, values):
        if value is not None and not show_values:
            continue
        center = bar.get_x() + bar.get_width() / 2
        ax.annotate("N/A" if value is None else format(value, format_spec),
                    (center, 0 if value is None else value), xytext=(0, 3),
                    textcoords="offset points", ha="center", va="bottom", fontsize=8)


def load_summaries(paths: list[Path]) -> list[tuple[str, dict]]:
    """Load activation result files and compute their summaries.

    中文：读取激活结果文件并计算绘图所需的汇总指标。
    """
    entries = []
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            print(f"{path}: cannot read result JSON: {exc}", file=sys.stderr)
            raise SystemExit(2)
        entries.append((str(path), compute_summary(data)))
    return entries


def confusion_matrix(summary: dict, output: Path, comparison: dict | None = None) -> None:
    """Render one or two split-specific routing confusion matrices in one PNG.

    中文：把一个或两个划分的正负例、加载状态和不可判定状态渲染在同一张 PNG 中。
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    summaries = [summary] if comparison is None else [summary, comparison]
    scale = max(max(item["overall"][key] for key in ("tp", "fn", "fp", "tn",
                                               "inconclusive_positive", "inconclusive_negative"))
                for item in summaries) or 1
    fig, axes = plt.subplots(1, len(summaries), figsize=(6 * len(summaries), 3.6),
                             squeeze=False)
    for ax, current in zip(axes[0], summaries):
        overall = current["overall"]
        # Rows are actual labels; columns are observed reads, non-reads, and infrastructure misses.
        matrix = [[overall["tp"], overall["fn"], overall["inconclusive_positive"]],
                  [overall["fp"], overall["tn"], overall["inconclusive_negative"]]]
        image = ax.imshow(matrix, cmap="Blues", aspect="auto", vmin=0, vmax=scale)
        ax.set_xticks(range(3), ["loaded", "not loaded", "inconclusive"])
        ax.set_yticks(range(2), ["positive", "negative"])
        ax.set_xlabel("predicted")
        ax.set_ylabel("actual")
        split = split_name(current)
        ax.set_title(f"{split.title()} routing" if split else "Routing confusion matrix")
        fig.colorbar(image, ax=ax, fraction=0.046)
        for row in range(2):
            for col in range(3):
                ax.text(col, row, str(matrix[row][col]), ha="center", va="center",
                        color="black" if matrix[row][col] < scale * 0.5 else "white")
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)


def per_skill_bars(summary: dict, output: Path) -> None:
    """Render per-skill precision, recall, and F1 bars.

    中文：绘制每个技能的 precision、recall 和 F1 对比条形图。
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    skills = list(summary["per_skill"])
    precision = [summary["per_skill"][s]["precision"] for s in skills]
    recall = [summary["per_skill"][s]["recall"] for s in skills]
    f1 = [summary["per_skill"][s]["f1"] for s in skills]
    x = list(range(len(skills)))
    width = 0.25
    fig, ax = plt.subplots(figsize=(max(7, len(skills) * 0.8), 4))
    for positions, values, label in (
        ([i - width for i in x], precision, "precision"),
        (x, recall, "recall"),
        ([i + width for i in x], f1, "f1"),
    ):
        bars = ax.bar(positions, [plotted_value(value) for value in values], width, label=label)
        annotate_bars(ax, bars, values, show_values=False)
    ax.set_xticks(x, skills, rotation=45, ha="right")
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("rate")
    ax.set_title("Precision, recall, and F1 per skill")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)


def iteration_trend(entries: list[tuple[str, dict]], output: Path) -> None:
    """Render comparable same-split routing metric trends in file order.

    中文：输入已确认属于可比较的同一数据集快照后，按文件顺序绘制路由指标趋势。
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    iterations = list(range(1, len(entries) + 1))
    keys = ("precision", "recall", "f1", "accuracy")
    fig, ax = plt.subplots(figsize=(7, 4))
    for key in keys:
        values = [entry[1]["overall"].get(key) for entry in entries]
        ax.plot(iterations, [plotted_value(value) for value in values], marker="o", label=key)
        for index, value in enumerate(values):
            if value is None:
                ax.annotate("N/A", (iterations[index], 0.02), ha="center", fontsize=8)
    ax.set_xticks(iterations)
    ax.set_xlabel("iteration (file order)")
    ax.set_ylabel("rate")
    ax.set_ylim(0, 1.05)
    ax.set_title("Routing metrics across iterations")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)


def overall_metrics(summary: dict, output: Path) -> None:
    """Render the main overall routing metrics.

    中文：绘制总体 precision、recall、specificity、F1、accuracy 和 coverage。
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = ("precision", "recall", "specificity", "f1", "accuracy", "coverage")
    values = [summary["overall"].get(name) for name in names]
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(names, [plotted_value(value) for value in values])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("rate")
    ax.set_title("Overall routing metrics")
    annotate_bars(ax, bars, values)
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)


def routing_radar(summary: dict, output: Path, label: str,
                  comparison: dict | None = None) -> None:
    """Plot per-skill precision, recall, and F1 with optional split comparison.

    中文：针对单份结果或两个划分绘制三个雷达面板，各轴对应一个 skill。

    Missing values / 缺失值：未定义的值标作 N/A 并断开曲线，不当成零值填充。
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    skills = sorted(set(summary["per_skill"]) | (set(comparison["per_skill"]) if comparison else set()))
    fig, axes = plt.subplots(3, 1, subplot_kw={"projection": "polar"}, figsize=(9, 16))
    for ax, metric in zip(axes, ("precision", "recall", "f1")):
        title = metric.upper() if metric == "f1" else metric.title()
        ax.set_title(title if comparison else f"{title} {label}", pad=20)
        if len(skills) < 3:
            ax.set_axis_off()
            ax.text(0.5, 0.5, "At least three skills required", transform=ax.transAxes,
                    ha="center", va="center")
            continue
        angles = [2 * math.pi * index / len(skills) for index in range(len(skills))]
        ax.set_theta_offset(math.pi / 2)
        ax.set_theta_direction(-1)
        series = [(label, summary)]
        if comparison is not None:
            series.append(("validation", comparison))
        ax.set_xticks(angles, [skill.removeprefix("python-") if all(
            item["per_skill"].get(skill, {}).get(metric) is not None for _, item in series
        ) else f"{skill.removeprefix('python-')} (N/A)" for skill in skills])
        ax.tick_params(axis="x", labelsize=10, pad=10)
        for angle, tick in zip(angles, ax.get_xticklabels()):
            tick.set_horizontalalignment("left" if math.sin(angle) > 0.3 else
                                         "right" if math.sin(angle) < -0.3 else "center")
        ax.set_ylim(0, 1)
        ax.set_yticks((0.25, 0.5, 0.75, 1.0))
        ax.tick_params(axis="y", labelsize=8)
        for series_label, item in series:
            values = [item["per_skill"].get(skill, {}).get(metric) for skill in skills]
            closed_values = [plotted_value(value) for value in values]
            closed_values.append(closed_values[0])
            line, = ax.plot(angles + angles[:1], closed_values, linewidth=1.8,
                            marker="o" if comparison else None, label=series_label)
            if comparison is None and all(value is not None for value in values):
                ax.fill(angles + angles[:1], closed_values, color=line.get_color(), alpha=0.16)
    if comparison is not None and len(skills) >= 3:
        fig.legend(axes[0].lines[:2], [label, "validation"], loc="lower center", ncol=2)
    fig.tight_layout(h_pad=2, rect=(0.03, 0.04 if comparison else 0, 0.97, 1))
    fig.savefig(output, dpi=150)
    plt.close(fig)


def latency_percentiles(summary: dict, output: Path) -> None:
    """Render mean, P50, P95, and maximum evaluation latency.

    中文：绘制评测耗时的均值、P50、P95 和最大值。
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = ("mean", "p50", "p95", "max")
    overall = summary["overall"]
    values = [
        overall.get("duration_seconds_mean"),
        overall.get("duration_seconds_p50"),
        overall.get("duration_seconds_p95"),
        overall.get("duration_seconds_max"),
    ]
    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(names, [plotted_value(value) for value in values])
    ax.set_ylim(0, max((value for value in values if value is not None), default=1) * 1.12 or 1)
    ax.set_ylabel("seconds")
    ax.set_title("Evaluation latency")
    annotate_bars(ax, bars, values, ".2f")
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)


def train_validation_metrics(entries: list[tuple[str, dict]], output: Path) -> bool:
    """Render train-versus-validation metrics when both splits are present.

    中文：同时存在训练集和验证集结果时绘制指标对比，并返回是否生成图表。
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    by_split = paired_splits(entries)
    if by_split is None:
        return False
    names = ("precision", "recall", "specificity", "f1", "accuracy", "coverage")
    train = [by_split["train"]["overall"].get(name) for name in names]
    validation = [by_split["validation"]["overall"].get(name) for name in names]
    x = list(range(len(names)))
    width = 0.38
    fig, ax = plt.subplots(figsize=(8, 4))
    for positions, values, label in (
        ([index - width / 2 for index in x], train, "train"),
        ([index + width / 2 for index in x], validation, "validation"),
    ):
        bars = ax.bar(positions, [plotted_value(value) for value in values], width, label=label)
        annotate_bars(ax, bars, values, show_values=False)
    ax.set_xticks(x, names, rotation=25, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("rate")
    ax.set_title("Train vs validation routing metrics")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return True


def train_validation_per_skill(entries: list[tuple[str, dict]], output: Path) -> bool:
    """Compare per-skill routing scores, denominators, and error counts by split.

    中文：并排展示每个 skill 在训练/验证集的 P、R、F1、有效分母及 FP/FN，不隐藏小样本误差。
    """
    by_split = paired_splits(entries)
    if by_split is None:
        return False
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    skills = sorted(set(by_split["train"]["per_skill"]) | set(by_split["validation"]["per_skill"]))
    fig, axes = plt.subplots(1, 2, figsize=(19, max(5, len(skills) * 0.8)))
    for ax, split in zip(axes, ("train", "validation")):
        summary = by_split[split]
        rows = [summary["per_skill"].get(skill, {}) for skill in skills]
        rates = [[plotted_value(row.get(key)) for key in ("precision", "recall", "f1")]
                 for row in rows]
        ax.imshow(rates, cmap="Blues", vmin=0, vmax=1, aspect="auto")
        ax.set_xticks(range(3), ["Precision", "Recall", "F1"])
        ax.set_yticks(range(len(skills)), [
            f"{skill}\nn={row.get('decided', 0) + row.get('inconclusive', 0)} "
            f"FP={row.get('fp', 0)} FN={row.get('fn', 0)}"
            for skill, row in zip(skills, rows)
        ])
        ax.tick_params(axis="y", labelsize=8, length=0)
        ax.tick_params(axis="x", length=0)
        ax.set_title(f"{split.title()} routing by skill (n={summary['overall']['total_trials']})")
        for index, row in enumerate(rows):
            tp, fp, fn = (row.get(key, 0) for key in ("tp", "fp", "fn"))
            for column, (key, numerator, denominator) in enumerate((
                ("precision", tp, tp + fp),
                ("recall", tp, tp + fn),
                ("f1", 2 * tp, 2 * tp + fp + fn),
            )):
                value = row.get(key)
                text = "N/A" if value is None else f"{value:.3f}\n{numerator}/{denominator}"
                ax.text(column, index, text, ha="center", va="center", fontsize=8,
                        color="white" if value is not None and value >= 0.65 else "black")
    fig.tight_layout(w_pad=4)
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return True


def main() -> int:
    """Load result files and render the supported chart set.

    中文：解析绘图参数，读取结果并生成项目支持的全部图表。
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path, help="activation result JSON files")
    parser.add_argument("--output-dir", type=Path, default=Path("evals/results"))
    parser.add_argument("--prefix", default="routing")
    args = parser.parse_args()

    try:
        import matplotlib  # noqa: F401
    except ImportError:
        print("matplotlib is not installed; run `python -m pip install matplotlib`", file=sys.stderr)
        return 2

    entries = load_summaries(args.files)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    paired = paired_splits(entries)
    confusion_matrix(paired["train"] if paired else entries[0][1],
                     args.output_dir / f"{args.prefix}-confusion.png",
                     paired["validation"] if paired else None)
    per_skill_bars(entries[0][1], args.output_dir / f"{args.prefix}-per-skill.png")
    overall_metrics(entries[0][1], args.output_dir / f"{args.prefix}-overall.png")
    radar_summary = paired["train"] if paired else entries[0][1]
    routing_radar(radar_summary, args.output_dir / f"{args.prefix}-radar.png",
                  "train" if paired else split_name(radar_summary) or "result",
                  paired["validation"] if paired else None)
    latency_percentiles(entries[0][1], args.output_dir / f"{args.prefix}-latency.png")
    if len(entries) > 1:
        if comparable_iterations(entries):
            iteration_trend(entries, args.output_dir / f"{args.prefix}-trend.png")
        train_validation_metrics(entries, args.output_dir / f"{args.prefix}-train-validation.png")
        train_validation_per_skill(entries, args.output_dir / f"{args.prefix}-train-validation-per-skill.png")
    print(f"wrote charts to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
