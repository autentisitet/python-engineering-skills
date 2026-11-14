#!/usr/bin/env python3
"""Check actual Codex app-server discovery without a model call."""
from __future__ import annotations
import argparse
import json
import os
import queue
import subprocess
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def link_skills(workspace: Path, skills_dir: Path) -> None:
    """Link repository skills into an isolated workspace.

    中文：把仓库技能链接到隔离工作区，供 Codex 发现检查使用。

    OS considerations / OS 考虑：POSIX 使用目录符号链接，Windows 使用 ``mklink /J`` junction；
    两者都避免复制技能内容，使发现结果仍指向真实源文件。
    """
    dest = workspace / '.agents/skills'
    dest.mkdir(parents=True)
    for source in skills_dir.iterdir():
        if not (source / 'SKILL.md').is_file():
            continue
        target = dest / source.name
        if os.name == 'nt':
            completed = subprocess.run(
                ['cmd', '/c', 'mklink', '/J', str(target), str(source)],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode != 0:
                raise OSError('cannot create skill junction')
        else:
            target.symlink_to(source, target_is_directory=True)


def check(workspace: Path, codex_home: Path, timeout: int = 30) -> dict:
    """Query the Codex app server and verify repository-scope skill discovery.

    中文：调用 Codex app server，验证所有仓库技能均被正确发现、启用并指向源文件。

    Networking / 计网考虑：app server 通过 stdio JSON-RPC 通信，不监听网络端口；响应由独立读取
    线程送入队列，并为每个请求设置单调时钟超时，避免 pipe 阻塞。
    """
    codex_home.mkdir(parents=True, exist_ok=True)
    environment = {key: value for key, value in os.environ.items() if key in {
        'PATH', 'PATHEXT', 'SYSTEMROOT', 'COMSPEC', 'TEMP', 'TMP',
        'TERM', 'LANG', 'LC_ALL', 'LC_CTYPE', 'NO_COLOR',
    }}
    environment['CODEX_HOME'] = str(codex_home)
    environment['HOME'] = str(codex_home)
    if os.name == 'nt':
        environment['USERPROFILE'] = str(codex_home)
    process = subprocess.Popen(['codex', 'app-server', '--stdio'], cwd=workspace,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, bufsize=1,
                               env=environment)
    lines: queue.Queue[str | None] = queue.Queue()

    def reader() -> None:
        """Forward app-server stdout lines into the response queue.

        中文：把 app server 的标准输出逐行送入响应队列。
        """
        try:
            for line in process.stdout:
                lines.put(line)
        finally:
            lines.put(None)

    reader_thread = threading.Thread(target=reader, daemon=True)
    reader_thread.start()

    def send(value):
        """Send one JSON-RPC message to the app server.

        中文：向 app server 发送一条 JSON-RPC 消息。
        """
        process.stdin.write(json.dumps(value) + '\n')
        process.stdin.flush()

    def receive(identifier):
        """Wait for one matching JSON-RPC response.

        中文：在超时范围内等待指定请求 ID 的 JSON-RPC 响应。

        Protocol / 协议：忽略通知和其他请求的响应，仅按 JSON-RPC ``id`` 匹配目标消息。
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                line = lines.get(timeout=max(0, deadline - time.monotonic()))
            except queue.Empty:
                break
            if line is None:
                break
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(value, dict):
                continue
            if value.get('id') == identifier:
                if 'error' in value:
                    raise RuntimeError('app-server rejected request; raw response omitted')
                result = value.get('result')
                if not isinstance(result, dict):
                    raise RuntimeError('app-server returned an invalid response; raw output omitted')
                return result
        raise RuntimeError('app-server timed out or exited; raw output omitted')
    try:
        send({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {'name': 'skill-eval', 'version': '1.0'}}})
        receive(1)
        send({'method': 'initialized', 'params': {}})
        send({'id': 2, 'method': 'skills/list', 'params': {'cwds': [str(workspace)], 'forceReload': True}})
        response = receive(2)
        expected = {p.name: (p / 'SKILL.md').resolve() for p in (ROOT / 'skills').iterdir() if (p / 'SKILL.md').is_file()}
        data = response.get('data')
        if not isinstance(data, list):
            raise RuntimeError('app-server returned invalid skills data; raw output omitted')
        found_by_name = {}
        duplicate_names = set()
        error_count = 0
        for entry in data:
            if not isinstance(entry, dict):
                raise RuntimeError('app-server returned an invalid discovery entry; raw output omitted')
            entry_errors = entry.get('errors', [])
            if not isinstance(entry_errors, list):
                raise RuntimeError('app-server returned invalid discovery errors; raw output omitted')
            error_count += len(entry_errors)
            skills = entry.get('skills', [])
            if not isinstance(skills, list):
                raise RuntimeError('app-server returned invalid skills; raw output omitted')
            for skill in skills:
                if not isinstance(skill, dict):
                    continue
                name = skill.get('name')
                path = skill.get('path')
                if name not in expected or not isinstance(path, str):
                    continue
                if name in found_by_name:
                    duplicate_names.add(name)
                    continue
                found_by_name[name] = {
                    'name': name,
                    'enabled': skill.get('enabled'),
                    'scope': skill.get('scope'),
                    'source_matches': Path(path).resolve() == expected[name],
                }
        found = [found_by_name[name] for name in sorted(found_by_name)]
        complete = error_count == 0 and not duplicate_names and all(
            name in found_by_name
            and found_by_name[name]['enabled'] is True
            and found_by_name[name]['source_matches']
            and found_by_name[name]['scope'] == 'repo'
            for name in expected
        )
        return {
            'expected': len(expected),
            'found': found,
            'duplicate_names': sorted(duplicate_names),
            'discovery_errors': error_count,
            'complete': complete,
        }
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        for stream in (process.stdin, process.stdout):
            try:
                stream.close()
            except AttributeError:
                pass


def main():
    """Run the discovery check CLI and optionally persist its JSON result.

    中文：执行技能发现检查命令，并按需写入 JSON 结果文件。
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='skill-discovery-') as temp:
        root = Path(temp)
        workspace = root / 'workspace'
        workspace.mkdir()
        link_skills(workspace, ROOT / 'skills')
        result = check(workspace, root / 'codex-home')
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding='utf-8')
    print(text, end='')
    return 0 if result['complete'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
