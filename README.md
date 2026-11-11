# python-engineering-skills

[English](README.md) | [中文](README_zh.md)

[![CI](https://github.com/autentisitet/python-engineering-skills/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/autentisitet/python-engineering-skills/actions/workflows/ci.yml)
[![Codex Skills](https://img.shields.io/badge/Codex-Skills-000000?logo=openai&logoColor=white)](https://developers.openai.com/codex/skills/)
[![Anthropic Agent Skills](https://img.shields.io/badge/Anthropic-Agent_Skills-D97757?logo=anthropic&logoColor=white)](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
[![Skill Evals](https://img.shields.io/badge/Anthropic-Skill_Evals-D97757?logo=anthropic&logoColor=white)](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#evaluation-and-iteration)

Codex skills for medium and large Python repositories. They turn recurring engineering decisions
into reusable review criteria, improve the reliability of Agent-generated changes, and aim to
substantially reduce the mental load of programmer code review.

## Skills

| Skill | Purpose |
| --- | --- |
| [python-domain-modeling](skills/python-domain-modeling/SKILL.md) | Python typing, dataclasses, Pydantic/settings, interfaces, invariants, and model copy semantics |
| [python-callable-caching](skills/python-callable-caching/SKILL.md) | Callable placement, properties, closures, caches, construction hooks, and resource cleanup |
| [python-sklearn-workflow](skills/python-sklearn-workflow/SKILL.md) | Leakage-safe splits, CV, preprocessing, search, diagnostic curves, PCA, and inspection |
| [python-cli-file-workflows](skills/python-cli-file-workflows/SKILL.md) | Streaming file CLIs, path ownership, tqdm output, and argparse contracts |
| [python-matplotlib-config](skills/python-matplotlib-config/SKILL.md) | Global style, CJK font fallback, `.mplstyle`, and Axes-first plotting calls |
| [python-loguru-logging](skills/python-loguru-logging/SKILL.md) | Exception boundaries, bound context, file lifecycle, queued logging, and shutdown |
| [python-media-processing](skills/python-media-processing/SKILL.md) | OpenCV/Pillow/Decord/PyAV configuration, library selection, sampling, and color spaces |
| [python-binary-buffers](skills/python-binary-buffers/SKILL.md) | `bytes`, `bytearray`, `memoryview`, binary protocols, ownership, and incremental I/O |

After installation, invoke a skill explicitly with names such as `$python-domain-modeling`, or let
its description auto-match a relevant task.

---

## Installation

Keep this repository as the versioned source and link only the required skills into a trusted
target project's `.agents/skills/` directory.

### Linux and WSL

```bash
make use TARGET=/path/to/python-project
```

The shell scripts require Bash 4+ and GNU `find`/`readlink`.

### Windows PowerShell

```powershell
$TargetProject = Join-Path $HOME "src\python-project"
.\scripts\links\use-skills.ps1 `
  -Target $TargetProject `
  -Skills python-domain-modeling,python-sklearn-workflow
```

PowerShell creates directory junctions. The source repository and target project must remain on
accessible local paths.

Remove managed links with:

```bash
make remove TARGET=/path/to/python-project
```

```powershell
.\scripts\links\remove-skills.ps1 -Target $TargetProject
```

The removal scripts preserve ordinary directories and links not managed by this repository.

---

## Updating

Symlink and junction installs use this repository as their live source. Pull or otherwise update the
repository, review the changes, and start a new agent session in the target project.

```bash
git pull
make validate
```

---

## Structure

```text
python-engineering-skills/
├── evals/
│   ├── train_queries.json
│   ├── validation_queries.json
│   └── results/                 # generated locally; ignored by Git
├── scripts/
│   ├── evals/                   # discovery, activation, and dataset validation
│   ├── links/                   # project-scoped install/remove helpers
│   └── packages/                # skill package linter
├── skills/
│   └── <skill-name>/
│       ├── SKILL.md
│       ├── agents/openai.yaml
│       └── references/
└── tests/
```

---

## Validation

Use Python 3.10+ and install the development dependency in a virtual environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
make validate PYTHON=.venv/bin/python
```

`make eval` runs `validate` plus a real Codex skill-discovery check, then prints the optional
model-backed steps; `make smoke` runs the cheap per-skill behavior smoke test.

On Windows, after installing `requirements.txt`:

```powershell
python -m scripts.packages.lint_skill_packages --strict-warnings
python -m scripts.evals.validate_evals
python -m unittest discover -s tests -p "test_*.py"
```

CI uses pinned Ubuntu 24.04 and Windows Server 2025 runners.

---

## Evaluation

`evals/train_queries.json` and `evals/validation_queries.json` contain 160 positive and negative
routing cases across the eight skills, split 60/40:

- training: 96 cases, with 6 positive and 6 negative cases per skill;
- validation: 64 held-out cases, with 4 positive and 4 negative cases per skill.

Validate the datasets without a model call:

```bash
python3 -m scripts.evals.validate_evals
```

Check actual Codex discovery without a model call:

```bash
python3 -m scripts.evals.check_skill_discovery \
  --output evals/results/discovery.json
```

Run observable activation trials through Codex only after accepting model cost and data transmission:

```bash
python3 -m scripts.evals.run_activation_evals evals/train_queries.json \
  --runs 3 \
  --jobs 1 \
  --allow-model-calls \
  --output evals/results/activation-train.json
```

For a cheaper behavior smoke test, set `--sample-per-label N` to run at most `N` positive and `N`
negative cases per skill. Values larger than the available cases use every available case without
repetition; zero, negative, and non-integer values are rejected.

| Result | Status |
| --- | --- |
| Codex skill discovery | 8/8 discovered and enabled |
| Training baseline, one run | 85 passed, 6 failed, 5 inconclusive out of 96 |
| Training after routing iteration, one run | 91 passed, 1 failed, 4 inconclusive out of 96 |
| Validation regression run | 61 passed, 0 failed, 3 inconclusive out of 64 after retrying inconclusive trials |

An inconclusive result means the run did not provide reliable evidence that the expected skill
entrypoint was read; it is reported separately from an observed routing mismatch.

---

## Design Conventions

- **Repeated decisions only.** A skill must repeatedly change implementation or review decisions;
  generic Python knowledge stays out.
- **Narrow routing.** Descriptions identify applicable work and adjacent exclusions; an incidental
  keyword does not justify loading a skill.
- **Progressive disclosure.** `SKILL.md` contains shared constraints and routing; conditional detail
  belongs in directly linked references.
- **Deterministic scripts only.** Add per-skill scripts only when repeated executable logic provides
  a clear reliability or token-cost benefit.
- **Platform layers stay separate.** `agents/openai.yaml` is optional Codex metadata, not a portable
  Agent Skills requirement.
- **Permissions remain external.** A skill can recommend a tool or script but cannot grant workspace,
  network, or execution permission.
- **Results have explicit limits.** Structure checks, routing observations, and artifact correctness
  are reported separately.

---

## License

This project is licensed under the [MIT License](LICENSE).
