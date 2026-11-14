#!/usr/bin/env python3
"""Parse Codex JSONL events into deterministic skill-activation evidence."""

from __future__ import annotations

import json
import os
import re
import shlex
from pathlib import Path


FRONTMATTER_PATTERN = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.DOTALL)
READ_COMMANDS = {"cat", "sed", "head", "tail", "rg", "grep", "type", "get-content"}
SHELL_SEPARATORS = {";", "&&", "||", "|", "&"}


def skill_markers(entry: Path) -> tuple[str, str]:
    """Return stable markers expected near the start of a rendered SKILL.md.

    中文：读取技能入口文件，返回名称与一级标题两个稳定证据标记。

    Design / 设计：只使用文件头部的名称和一级标题，避免依赖易变化的正文，同时拒绝缺失
    frontmatter 或非 UTF-8 文件，防止把不完整输出误判为真实读取。
    """
    try:
        text = entry.read_text(encoding="utf-8").replace("\r\n", "\n")
    except (OSError, UnicodeError) as error:
        raise RuntimeError(f"cannot read skill entrypoint: {entry}") from error
    match = FRONTMATTER_PATTERN.match(text)
    if not match:
        raise RuntimeError(f"malformed skill frontmatter: {entry}")
    heading = next((line for line in text[match.end():].splitlines() if line.startswith("# ")), "")
    if not heading:
        raise RuntimeError(f"missing skill heading: {entry}")
    return f"name: {entry.parent.name}", heading


def build_markers(skills_dir: Path) -> list[tuple[str, str, str]]:
    """Return activation markers for every skill package.

    中文：扫描技能目录并为每个技能构建激活证据标记。
    """
    return [
        (source.name, *skill_markers(source / "SKILL.md"))
        for source in skills_dir.iterdir()
        if (source / "SKILL.md").is_file()
    ]


def command_event_matches(
    event: dict, target_name: str, markers: list[tuple[str, str, str]]
) -> bool:
    """Return whether a successful file-reading command emitted target markers.

    中文：仅在成功的文件读取命令输出目标技能完整入口标记时返回真。

    Evidence / 证据：解析 shell 命令以排除打印标记的命令；仍是命令与输出的代理证据，
    不是 OS 级文件访问审计。
    """
    if event.get("type") != "item.completed":
        return False
    item = event.get("item")
    if not isinstance(item, dict) or item.get("type") != "command_execution":
        return False
    if item.get("exit_code") != 0:
        return False
    command = item.get("command", "")
    output = item.get("aggregated_output", "")
    if not isinstance(command, str) or not isinstance(output, str):
        return False
    try:
        lexer = shlex.shlex(command, posix=os.name != "nt", punctuation_chars=";&|")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return False
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token in SHELL_SEPARATORS:
            segments.append([])
        else:
            segments[-1].append(token)
    reads_entry = any(
        segment and segment[0].lower() in READ_COMMANDS
        and any(argument.strip("\"'").replace("\\", "/").split("/")[-1] == "SKILL.md"
                for argument in segment[1:])
        for segment in segments
    )
    if not reads_entry:
        return False
    output = output.replace("\r\n", "\n")
    return any(
        name == target_name
        and name_marker in output
        and heading_marker in output
        for name, name_marker, heading_marker in markers
    )


def observe(jsonl_output: str, markers: list[tuple[str, str, str]]) -> dict:
    """Extract activation evidence and usage from Codex JSONL output.

    中文：从 Codex JSONL 输出中提取技能读取证据、完成状态和安全的 token 用量。

    Protocol / 协议：逐行容忍非 JSON 噪声，只保留已知整数 usage 字段，避免未知事件或敏感
    payload 被复制到评测结果。
    """
    observed: set[str] = set()
    finished = False
    usage = None
    for line in jsonl_output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "turn.completed":
            finished = True
            usage = event.get("usage")
        observed.update(
            name for name, _, _ in markers
            if command_event_matches(event, name, markers)
        )
    return {
        "observed_reads": sorted(observed),
        "turn_completed": finished,
        "usage": {
            key: value
            for key, value in (usage or {}).items()
            if key in ("input_tokens", "cached_input_tokens", "output_tokens")
            and type(value) is int
        },
    }
