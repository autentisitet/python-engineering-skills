#!/usr/bin/env python3
"""Observe skill entrypoint reads for unchanged requests in fresh Codex sessions."""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from scripts.evals.activation_evidence import (
    build_markers,
    command_event_matches,
    observe,
)
from scripts.evals.check_skill_discovery import link_skills
from scripts.evals.summarize_evals import skills_digest
from scripts.evals.validate_evals import case_sha256, load_cases
from scripts.packages.lint_skill_packages import NAME_PATTERN

ROOT = Path(__file__).resolve().parents[2]
BASE_ENV_NAMES = {
    "COMSPEC", "LANG", "LC_ALL", "LC_CTYPE", "NO_COLOR", "PATH", "PATHEXT",
    "SYSTEMROOT", "TEMP", "TERM", "TMP", "TZ", "HOME", "USERPROFILE", "CODEX_HOME",
}
DEFAULT_AUTH_ENV_NAMES = {"CODEX_API_KEY", "OPENAI_API_KEY"}


def sample_cases(cases: list[dict], per_label: int | None) -> list[dict]:
    """Sample each skill and label deterministically.

    中文：按技能和正负标签稳定抽样，保证重复运行选择相同查询。
    """
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


@dataclass(frozen=True)
class CodexOptions:
    """Model and provider settings applied to every fresh ``codex exec`` session."""
    model: str | None = None
    profile: str | None = None
    reasoning_effort: str | None = None
    pass_env: tuple[str, ...] = ()


def codex_command(options: CodexOptions | None = None) -> list[str]:
    """Build the ``codex exec`` command using the caller's Codex login.

    中文：使用调用者已有的 Codex 登录构建命令，并应用模型、输出限制与安全配置。

    Security / 安全：固定禁用子代理、bundled skills 和工具环境继承，避免本机配置污染路由测量。
    """
    options = options or CodexOptions()
    command = [
        'codex', 'exec', '--ephemeral', '--json', '--skip-git-repo-check',
        '--sandbox', 'read-only',
    ]
    if options.profile is not None:
        command += ['--profile', options.profile]
    if options.model is not None:
        command += ['--model', options.model]
    if options.reasoning_effort is not None:
        command += ['--config', f'model_reasoning_effort={options.reasoning_effort}']
    command += ['--config', 'features.multi_agent=false',
                '--config', 'skills.bundled.enabled=false',
                '--config', 'shell_environment_policy.inherit=none']
    return command + ['-']


def codex_options_dict(options: CodexOptions) -> dict:
    """Serialize Codex options used for resume compatibility.

    中文：序列化影响评测行为的 Codex 参数，用于拒绝不兼容的历史 trial。
    """
    return {
        "model": options.model,
        "profile": options.profile,
        "reasoning_effort": options.reasoning_effort,
        "pass_env": list(options.pass_env),
        "multi_agent_enabled": False,
    }


def detect_codex_version(environment: dict[str, str]) -> str | None:
    """Read the installed Codex CLI version without starting a model session.

    中文：通过 ``codex --version`` 获取真实 Codex 版本，不发起模型调用。
    """
    try:
        completed = subprocess.run(
            ["codex", "--version"], capture_output=True, text=True,
            timeout=5, check=False, env=environment,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    version = completed.stdout.strip()
    return version if completed.returncode == 0 and version else None


def resume_is_compatible(payload: dict, skills_sha256: str, options: CodexOptions,
                         codex_version: str | None) -> bool:
    """Reuse trials only when skills, Codex runtime, and evaluation options match.

    中文：仅在技能摘要、Codex 版本和评测参数一致时复用已有 trial。

    Reproducibility / 可复现性：查询内容另外按 case 摘要比较，允许数据集部分更新后复用未变的查询。
    """
    return (
        codex_version is not None
        and payload.get("codex_version") == codex_version
        and payload.get("skills_sha256") == skills_sha256
        and payload.get("codex_options") == codex_options_dict(options)
    )


def codex_env(pass_env: tuple[str, ...] = ()) -> dict[str, str]:
    """Preserve Codex home and selected provider variables for the CLI process.

    中文：保留调用者的 Codex home 和选定的 provider 环境变量，不重定向登录目录。

    Security / 安全：仅向 Codex 进程传递白名单变量；工具命令仍由 CLI 配置禁止继承环境。
    """
    allowed = BASE_ENV_NAMES | DEFAULT_AUTH_ENV_NAMES | set(pass_env)
    return {name: value for name, value in os.environ.items() if name in allowed}


@dataclass
class RunResult:
    stdout: str
    returncode: int
    triggered: bool
    thread_id: str | None = None


def run_streaming(command: list[str], query: str, cwd: Path, env: dict[str, str],
                  timeout: int, stop) -> RunResult:
    """Stream ``codex exec`` events until completion, timeout, or decisive evidence.

    中文：流式读取 Codex 事件，在完成、超时或出现决定性证据时停止子进程。

    OS considerations / OS 考虑：使用独立 reader thread 而非 ``selectors`` 监听 pipe，以兼容 Windows
    普通管道；超时时先终止、再强制 kill，避免遗留子进程。
    """
    process = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, cwd=cwd, env=env, bufsize=1,
    )
    try:
        process.stdin.write(query)
    except (BrokenPipeError, OSError):
        pass
    finally:
        try:
            process.stdin.close()
        except OSError:
            pass

    lines: list[str] = []
    triggered = threading.Event()
    thread_id = None

    def reader() -> None:
        """Read JSONL output and capture the independent session ID.

        中文：读取 JSONL 输出，记录独立会话 ID 和提前停止信号。
        """
        nonlocal thread_id
        try:
            for line in process.stdout:
                lines.append(line)
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    if event.get("type") == "thread.started" and isinstance(event.get("thread_id"), str):
                        thread_id = event["thread_id"]
                if isinstance(event, dict) and stop(event):
                    triggered.set()
                    return
        except (OSError, ValueError):
            pass

    reader_thread = threading.Thread(target=reader, daemon=True)
    reader_thread.start()
    deadline = time.monotonic() + timeout
    try:
        while True:
            if triggered.is_set():
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                break
            if process.poll() is not None:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                process.wait()
                raise subprocess.TimeoutExpired(command, timeout)
            triggered.wait(timeout=min(1.0, remaining))
    finally:
        reader_thread.join(timeout=5)
    return RunResult(
        stdout=''.join(lines),
        returncode=process.returncode or 0,
        triggered=triggered.is_set(),
        thread_id=thread_id,
    )


def run_case(case: dict, timeout: int, options: CodexOptions | None = None) -> dict:
    """Execute one query in a fresh workspace and return its routing outcome.

    中文：在全新工作区运行单条查询，依据真实技能读取证据返回路由结果。

    Isolation / 隔离：每条查询使用独立临时工作区；只有 timeout 和 Codex 进程 I/O 故障会转为
    infrastructure failure，内部程序错误直接暴露。
    """
    started = time.monotonic()
    options = options or CodexOptions()
    markers = build_markers(ROOT / 'skills')
    with tempfile.TemporaryDirectory(prefix='skill-activation-') as temp:
        workspace = Path(temp)
        link_skills(workspace, ROOT / 'skills')
        try:
            completed = run_streaming(
                codex_command(options), case['query'], workspace,
                codex_env(options.pass_env), timeout,
                stop=lambda event: command_event_matches(event, case['skill'], markers),
            )
        except subprocess.TimeoutExpired:
            return {'status': 'inconclusive', 'infrastructure_failure': True,
                    'reason': 'timeout',
                    'duration_seconds': round(time.monotonic() - started, 3)}
        except OSError:
            return {'status': 'inconclusive', 'infrastructure_failure': True,
                    'reason': 'evaluation_unavailable',
                    'duration_seconds': round(time.monotonic() - started, 3)}

        if completed.triggered:
            status = 'pass' if case['should_trigger'] else 'fail'
            return {'status': status, 'observed_skill_read': True,
                    'turn_completed': False, 'usage': {},
                    'thread_id': getattr(completed, 'thread_id', None),
                    'duration_seconds': round(time.monotonic() - started, 3)}
        if completed.returncode != 0:
            return {'status': 'inconclusive', 'infrastructure_failure': True,
                    'reason': 'agent_process_failed',
                    'thread_id': getattr(completed, 'thread_id', None),
                    'duration_seconds': round(time.monotonic() - started, 3)}
        evidence = observe(completed.stdout, markers)
        if not evidence['turn_completed']:
            return {'status': 'inconclusive', 'infrastructure_failure': True,
                    'reason': 'completion_event_missing',
                    'thread_id': getattr(completed, 'thread_id', None),
                    'duration_seconds': round(time.monotonic() - started, 3)}
        loaded = case['skill'] in evidence['observed_reads']
        status = 'pass' if loaded == case['should_trigger'] else 'fail'
        return {'status': status, 'observed_skill_read': loaded, **evidence,
                'thread_id': getattr(completed, 'thread_id', None),
                'duration_seconds': round(time.monotonic() - started, 3)}


def main():
    """Run the activation-evaluation CLI and persist progress atomically.

    中文：执行激活评测 CLI，并在每个 trial 完成后原子保存进度。

    Concurrency / 并发：预检成功后才创建线程池；每个 future 完成即持久化，限制并发度以控制模型成本
    和共享认证状态压力。
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    parser.add_argument('--allow-model-calls', action='store_true')
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--jobs', type=int, default=1)
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--model', default=None,
                        help='pass --model through to every fresh codex exec session')
    parser.add_argument('--profile', default=None,
                        help='pass --profile through to every fresh codex exec session')
    parser.add_argument('--reasoning-effort', default=None,
                        help='override model_reasoning_effort (e.g. low/medium/high)')
    parser.add_argument('--pass-env', action='append', default=[], metavar='NAME',
                        help='pass one named host variable to Codex; repeatable')
    parser.add_argument('--sample-per-label', type=int, default=None,
                        help='run at most this many positive and negative cases per skill')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--resume', type=Path, default=None,
                        help='reuse matching trials from a previous result file')
    args = parser.parse_args()
    if not args.allow_model_calls or args.runs < 1 or not 1 <= args.jobs <= 4:
        parser.error('explicit --allow-model-calls, positive --runs and --jobs 1..4 required')
    if args.timeout < 1:
        parser.error('--timeout must be at least 1 second')
    if args.sample_per_label is not None and args.sample_per_label < 1:
        parser.error('--sample-per-label must be at least 1')
    if any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name) for name in args.pass_env):
        parser.error('--pass-env values must be environment variable names')
    options = CodexOptions(
        model=args.model,
        profile=args.profile,
        reasoning_effort=args.reasoning_effort,
        pass_env=tuple(dict.fromkeys(args.pass_env)),
    )
    installed_codex_version = detect_codex_version(codex_env(options.pass_env))
    cases, errors = load_cases(args.dataset)
    if errors or not cases or any(not NAME_PATTERN.fullmatch(case['skill']) or not (ROOT/'skills'/case['skill']/'SKILL.md').is_file() for case in cases):
        parser.error('invalid or empty dataset')
    cases = sample_cases(cases, args.sample_per_label)
    rows = [{'id': c['id'], 'skill': c['skill'], 'category': c['category'],
             'should_trigger': c['should_trigger'],
             'case_sha256': case_sha256(c), 'trials': []} for c in cases]
    dataset_payload = json.loads(args.dataset.read_text(encoding='utf-8'))
    skills_sha256 = skills_digest(ROOT)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    def save():
        """Persist the current evaluation payload atomically.

        中文：原子写入当前评测状态，支持中断后检查与显式 resume。
        """
        trials = [t for row in rows for t in row['trials']]
        payload = {'evaluation_kind': 'observed_entrypoint_reads',
                   'dataset_version': dataset_payload.get('version'),
                   'dataset_split': dataset_payload.get('split'),
                   'dataset_split_seed': dataset_payload.get('split_seed'),
                   'skills_sha256': skills_sha256,
                   'dataset_sha256': hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
                   'sample_per_label': args.sample_per_label,
                   'codex_version': installed_codex_version,
                   'codex_options': codex_options_dict(options),
                   'completed_trials': len(trials), 'expected_trials': len(cases)*args.runs,
                   'passes': sum(t['status']=='pass' for t in trials),
                   'failures': sum(t['status']=='fail' for t in trials),
                   'inconclusive': sum(t['status']=='inconclusive' for t in trials), 'results': rows}
        tmp = args.output.with_suffix('.tmp')
        tmp.write_text(json.dumps(payload, indent=2)+'\n', encoding='utf-8')
        tmp.replace(args.output)
        return payload
    if args.resume is not None:
        try:
            previous = json.loads(args.resume.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            print(f"warning: cannot read --resume file: {error}", file=sys.stderr, flush=True)
            previous = None
        if previous and resume_is_compatible(
            previous, skills_sha256, options, installed_codex_version
        ):
            previous_rows = {row.get("id"): row for row in previous.get("results", [])}
            for row in rows:
                old = previous_rows.get(row["id"])
                if old and old.get("case_sha256") == row["case_sha256"]:
                    row["trials"] = list(old.get("trials", []))[:args.runs]
    payload = save()
    if len(rows[0]['trials']) < args.runs:
        preflight = run_case(cases[0], args.timeout, options)
        rows[0]['trials'].append(preflight)
        payload = save()
        if preflight.get('infrastructure_failure') and preflight.get('reason') in ('agent_process_failed', 'evaluation_unavailable'):
            print(f"preflight failed: {preflight.get('reason')}; remaining model calls were not started", file=sys.stderr, flush=True)
            return 2
    tasks = []
    for index, case in enumerate(cases):
        remaining = args.runs - len(rows[index]['trials'])
        if remaining > 0:
            tasks.extend((index, case) for _ in range(remaining))
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        pending = {pool.submit(run_case, case, args.timeout, options): index for index, case in tasks}
        for future in concurrent.futures.as_completed(pending):
            trial = future.result()
            rows[pending[future]]['trials'].append(trial)
            payload = save()
            print(f"{payload['completed_trials']}/{payload['expected_trials']} activation trials; {payload['passes']} passes, {payload['failures']} failures, {payload['inconclusive']} inconclusive", file=sys.stderr, flush=True)
    return 0 if payload['passes'] == payload['expected_trials'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
