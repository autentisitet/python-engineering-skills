#!/usr/bin/env python3
"""Convert eval query JSON files to and from Excel-friendly CSV files."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path


COLUMNS = ("id", "skill", "category", "query", "should_trigger")
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def escape_excel_cell(value: str) -> str:
    """Escape formula-like cells while preserving reversible CSV round trips.

    中文：转义公式前缀和前导单引号，避免 Excel 执行单元格内容并保持可逆转换。

    Security / 安全：以单引号前缀中和 ``= + - @`` 等公式起始字符，防止审查不可信 CSV 时
    触发 spreadsheet formula injection。
    """
    if value.startswith("'") or value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def unescape_excel_cell(value: str) -> str:
    """Reverse only escapes emitted by :func:`escape_excel_cell`.

    中文：仅还原本转换器添加的 Excel 安全转义，不修改普通文本。
    """
    if value.startswith("''") or (
        value.startswith("'") and value[1:].startswith(FORMULA_PREFIXES)
    ):
        return value[1:]
    return value


def read_json_queries(path: Path) -> list[dict]:
    """Read the query array from a JSON dataset envelope.

    中文：读取 JSON 数据集外层对象中的查询数组，并校验基本结构。
    """
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read JSON: {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"top-level value must be an object: {path}")
    queries = value.get("queries")
    if not isinstance(queries, list):
        raise ValueError(f"`queries` must be an array: {path}")
    return queries


def write_csv(path: Path, queries: list[dict]) -> None:
    """Write queries as an Excel-friendly and formula-safe UTF-8 CSV.

    中文：把查询写为带 BOM 且防公式注入的 Excel 友好 CSV。

    Compatibility / 兼容：使用 UTF-8 BOM 改善 Excel 编码识别，并让 ``csv`` 模块负责引用与换行，
    不手工拼接字段。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="raise")
        writer.writeheader()
        for query in queries:
            if set(query) != set(COLUMNS):
                raise ValueError(f"unexpected query fields: {sorted(query)}")
            row = {
                key: escape_excel_cell(value) if isinstance(value, str) else value
                for key, value in query.items()
            }
            row["should_trigger"] = "true" if row["should_trigger"] else "false"
            writer.writerow(row)


def parse_bool(value: str) -> bool:
    """Parse common human-friendly boolean spellings.

    中文：解析 CSV 中常见的布尔值拼写，不接受含糊值。
    """
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"should_trigger must be true/false, got {value!r}")


def read_csv_queries(path: Path) -> list[dict]:
    """Read and normalize queries from the canonical CSV columns.

    中文：按固定列顺序读取 CSV 查询，并还原安全转义与布尔值。
    """
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ValueError(f"missing header: {path}")
            if [name.strip() for name in reader.fieldnames] != list(COLUMNS):
                raise ValueError(
                    f"header must be {', '.join(COLUMNS)}: {path}"
                )
            queries: list[dict] = []
            for line_number, row in enumerate(reader, start=2):
                try:
                    queries.append({
                        "id": unescape_excel_cell(row["id"].strip()),
                        "skill": unescape_excel_cell(row["skill"].strip()),
                        "category": unescape_excel_cell(row["category"].strip()),
                        "query": unescape_excel_cell(row["query"].strip()),
                        "should_trigger": parse_bool(row["should_trigger"]),
                    })
                except KeyError as error:
                    raise ValueError(f"{path}:{line_number}: missing column {error}") from error
    except (OSError, UnicodeError, csv.Error) as error:
        raise ValueError(f"cannot read CSV: {path}: {error}") from error
    return queries


def file_sha256(path: Path) -> str:
    """Return the SHA-256 digest of one file.

    中文：计算并返回单个文件的 SHA-256 摘要。
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, queries: list[dict], version: int, split: str, split_seed: int) -> bool:
    """Write JSON atomically and report whether its content changed.

    中文：原子写入 JSON 数据集，仅在内容变化时替换目标文件并返回真。

    OS considerations / OS 考虑：临时文件创建在目标同目录后用 ``os.replace`` 替换，保证同一文件系统
    上的原子性，并避免跨设备 rename 失败。
    """
    payload = {
        "version": version,
        "split": split,
        "split_seed": split_seed,
        "queries": queries,
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    new_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if path.exists() and file_sha256(path) == new_digest:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
            handle.write(text)
            temporary = Path(handle.name)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return True


def to_csv(args: argparse.Namespace) -> int:
    """Execute the JSON-to-CSV subcommand.

    中文：执行 JSON 转 CSV 子命令并返回进程退出码。
    """
    try:
        queries = read_json_queries(args.source)
        write_csv(args.destination, queries)
    except (ValueError, OSError, UnicodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"wrote {args.destination} ({len(queries)} queries)")
    return 0


def to_json(args: argparse.Namespace) -> int:
    """Execute the CSV-to-JSON subcommand.

    中文：执行 CSV 转 JSON 子命令并返回进程退出码。
    """
    try:
        queries = read_csv_queries(args.source)
        changed = write_json(args.destination, queries, args.version, args.split, args.split_seed)
    except (ValueError, OSError, UnicodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    action = "wrote" if changed else "unchanged"
    print(f"{action} {args.destination} ({len(queries)} queries)")
    return 0


def main() -> int:
    """Parse conversion CLI arguments and dispatch the selected subcommand.

    中文：解析转换命令行参数并分派到对应子命令。
    """
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    json_to_csv = subparsers.add_parser("to-csv", help="convert a JSON query set to CSV")
    json_to_csv.add_argument("source", type=Path)
    json_to_csv.add_argument("destination", type=Path)
    json_to_csv.set_defaults(func=to_csv)

    csv_to_json = subparsers.add_parser("to-json", help="convert a CSV query set back to JSON")
    csv_to_json.add_argument("source", type=Path)
    csv_to_json.add_argument("destination", type=Path)
    csv_to_json.add_argument("--version", type=int, default=1)
    csv_to_json.add_argument("--split", choices=("train", "validation"), required=True)
    csv_to_json.add_argument("--split-seed", type=int, required=True)
    csv_to_json.set_defaults(func=to_json)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
