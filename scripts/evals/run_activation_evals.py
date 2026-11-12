#!/usr/bin/env python3
"""Observe skill entrypoint reads for unchanged requests in fresh Codex sessions."""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from scripts.evals.check_skill_discovery import link_skills
from scripts.evals.validate_evals import load_cases
from scripts.packages.lint_skill_packages import NAME_PATTERN

ROOT = Path(__file__).resolve().parents[2]
FRONTMATTER_PATTERN = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.DOTALL)


def skill_markers(entry: Path) -> tuple[str, str]:
    """Return stable markers expected near the start of a rendered SKILL.md."""
    try:
        text = entry.read_text(encoding='utf-8').replace('\r\n', '\n')
    except (OSError, UnicodeError) as error:
        raise RuntimeError(f'cannot read skill entrypoint: {entry}') from error
    match = FRONTMATTER_PATTERN.match(text)
    if not match:
        raise RuntimeError(f'malformed skill frontmatter: {entry}')
    name_marker = f"name: {entry.parent.name}"
    heading = next((line for line in text[match.end():].splitlines() if line.startswith('# ')), '')
    if not heading:
        raise RuntimeError(f'missing skill heading: {entry}')
    return name_marker, heading


def observe(jsonl_output: str) -> dict:
    """Observe successful commands that emitted stable SKILL.md entrypoint markers."""
    observed = set()
    finished = False
    usage = None
    markers = []
    for source in (ROOT / 'skills').iterdir():
        entry = source / 'SKILL.md'
        if entry.is_file():
            markers.append((source.name, *skill_markers(entry)))
    for line in jsonl_output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get('type') == 'turn.completed':
            finished = True
            usage = event.get('usage')
        item = event.get('item', {})
        if not isinstance(item, dict) or event.get('type') != 'item.completed':
            continue
        if item.get('type') != 'command_execution' or item.get('exit_code') != 0:
            continue
        command = item.get('command', '')
        command_output = item.get('aggregated_output', '').replace('\r\n', '\n')
        for name, name_marker, heading_marker in markers:
            command_mentions_entry = 'SKILL.md' in command and (
                name in command or name_marker in command_output
            )
            if command_mentions_entry and name_marker in command_output and heading_marker in command_output:
                observed.add(name)
    return {'observed_reads': sorted(observed), 'turn_completed': finished,
            'usage': {key: value for key, value in (usage or {}).items() if key in ('input_tokens', 'cached_input_tokens', 'output_tokens') and type(value) is int}}


def sample_cases(cases: list[dict], per_label: int | None) -> list[dict]:
    """Keep at most ``per_label`` positive and negative cases per skill, deterministically."""
    if per_label is None:
        return cases
    grouped: dict[tuple[str, bool], list[dict]] = {}
    for case in cases:
        grouped.setdefault((case['skill'], case['should_trigger']), []).append(case)
    sampled: list[dict] = []
    for key in sorted(grouped):
        ordered = sorted(grouped[key], key=lambda item: item['id'])
        sampled.extend(ordered[:per_label])
    return sorted(sampled, key=lambda item: (item['skill'], item['id']))


def codex_command() -> list[str]:
    """Return the complete portable command; user config supplies only normal Codex defaults/auth."""
    return [
        'codex', 'exec', '--ephemeral', '--json', '--skip-git-repo-check',
        '--sandbox', 'read-only', '-',
    ]


def run_case(case: dict, timeout: int) -> dict:
    try:
        with tempfile.TemporaryDirectory(prefix='skill-activation-') as temp:
            workspace = Path(temp)
            link_skills(workspace, ROOT / 'skills')
            started = time.monotonic()
            completed = subprocess.run(
                codex_command(), input=case['query'], cwd=workspace,
                capture_output=True, text=True, timeout=timeout, check=False,
            )
            if completed.returncode != 0:
                return {'status': 'inconclusive', 'error': 'agent process failed; raw output omitted'}
            evidence = observe(completed.stdout)
            if not evidence['turn_completed']:
                return {'status': 'inconclusive', 'error': 'completion event unavailable'}
            loaded = case['skill'] in evidence['observed_reads']
            status = 'pass' if loaded == case['should_trigger'] else ('fail' if loaded else 'inconclusive')
            return {'status': status, 'observed_skill_read': loaded, **evidence,
                    'duration_seconds': round(time.monotonic() - started, 3)}
    except (OSError, RuntimeError, UnicodeError, ValueError, subprocess.TimeoutExpired):
        return {'status': 'inconclusive', 'error': 'evaluation unavailable or timed out; raw output omitted'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    parser.add_argument('--allow-model-calls', action='store_true')
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('--sample-per-label', type=int, default=None,
                        help='run at most this many positive and negative cases per skill')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.allow_model_calls or args.runs < 1 or not 1 <= args.jobs <= 4:
        parser.error('explicit --allow-model-calls, positive --runs and --jobs 1..4 required')
    if args.timeout < 1:
        parser.error('--timeout must be at least 1 second')
    if args.sample_per_label is not None and args.sample_per_label < 1:
        parser.error('--sample-per-label must be at least 1')
    cases, errors = load_cases(args.dataset)
    if errors or not cases or any(not NAME_PATTERN.fullmatch(case['skill']) or not (ROOT/'skills'/case['skill']/'SKILL.md').is_file() for case in cases):
        parser.error('invalid or empty dataset')
    cases = sample_cases(cases, args.sample_per_label)
    rows = [{'id': c['id'], 'skill': c['skill'], 'should_trigger': c['should_trigger'], 'trials': []} for c in cases]
    digest = hashlib.sha256()
    for path in sorted((ROOT / 'skills').rglob('*')):
        if path.is_file():
            digest.update(str(path.relative_to(ROOT)).encode())
            digest.update(path.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    def save():
        trials = [t for row in rows for t in row['trials']]
        payload = {'evaluation_kind': 'observed_entrypoint_reads', 'skills_sha256': digest.hexdigest(),
                   'dataset_sha256': hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
                   'sample_per_label': args.sample_per_label,
                   'completed_trials': len(trials), 'expected_trials': len(cases)*args.runs,
                   'passes': sum(t['status']=='pass' for t in trials),
                   'failures': sum(t['status']=='fail' for t in trials),
                   'inconclusive': sum(t['status']=='inconclusive' for t in trials), 'results': rows}
        tmp = args.output.with_suffix('.tmp')
        tmp.write_text(json.dumps(payload, indent=2)+'\n', encoding='utf-8')
        tmp.replace(args.output)
        return payload
    payload = save()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        pending = {pool.submit(run_case, case, args.timeout): index for index, case in enumerate(cases) for _ in range(args.runs)}
        for future in concurrent.futures.as_completed(pending):
            trial = future.result()
            rows[pending[future]]['trials'].append(trial)
            payload = save()
            print(f"{payload['completed_trials']}/{payload['expected_trials']} activation trials; {payload['passes']} passes, {payload['failures']} failures, {payload['inconclusive']} inconclusive", file=sys.stderr, flush=True)
    return 0 if payload['passes'] == payload['expected_trials'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
