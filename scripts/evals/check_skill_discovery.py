#!/usr/bin/env python3
"""Check actual Codex app-server discovery without a model call."""
from __future__ import annotations
import argparse
import json
import os
import selectors
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def link_skills(workspace: Path, skills_dir: Path) -> None:
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


def check(workspace: Path, timeout: int = 30) -> dict:
    process = subprocess.Popen(['codex', 'app-server', '--stdio'], cwd=workspace,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, bufsize=1)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    def send(value):
        process.stdin.write(json.dumps(value) + '\n')
        process.stdin.flush()
    def receive(identifier):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not selector.select(timeout=max(0, deadline - time.monotonic())):
                break
            line = process.stdout.readline()
            if not line:
                break
            value = json.loads(line)
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
        selector.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        for stream in (process.stdin, process.stdout):
            stream.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='skill-discovery-') as temp:
        workspace = Path(temp)
        link_skills(workspace, ROOT / 'skills')
        result = check(workspace)
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding='utf-8')
    print(text, end='')
    return 0 if result['complete'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
