# Changelog

Development milestones are listed below. Remote `main` contains the v0.1.0 baseline; the
v0.2.0 and v0.3.0 sections classify uncommitted changes, not independent Git snapshots.
Before tagging both versions, create and verify distinct commits; two tags on a single
combined commit would not preserve a v0.2.0 release state.

## [v0.3.0] - Unreleased

### Added

- Added per-skill train/validation comparisons with sample counts, FP/FN, and metric
  denominators; compared both splits in a single radar figure and a single confusion figure.
- Added explicit-invocation artifact acceptance samples for eight skills and a human-reviewed,
  scrubbed report template. Artifact checks run in separate temporary projects, not this repo.
- Added bilingual version badges, historical routing charts, and documentation of result
  provenance, interpretation, and publication boundaries.

### Changed

- Report historical routing metrics separately from artifact quality; no new model-backed
  full-run or quality baseline is claimed.
- Simplified eval documentation and aligned the English and Chinese READMEs.

### Fixed

- Stop treating train and validation as successive iterations. Only plot a trend for
  comparable repeated runs of the same split; mark undefined rates N/A rather than zero.
- Corrected chart labels and confusion-matrix contrast, and fixed resume with identical
  input/output paths and evaluated-subset freshness.

---

## [v0.2.0] - Unreleased

### Added

- Added versioned train/validation routing datasets with 176 labeled queries, categories,
  and deterministic JSON/CSV conversion with spreadsheet-formula protection.
- Added activation-result summarization, retry-case extraction, cross-model checks,
  expanded model-free skill discovery, and optional diagnostic plotting.
- Added precision, recall, F1, accuracy, specificity, balanced accuracy, FPR/FNR,
  per-query trigger rates, inconclusive rate, coverage, latency percentiles, and token usage.
- Added reproducible Python dependency metadata (`pyproject.toml`, `uv.lock`, and hashed
  `requirements.txt`) and Dependabot updates.

### Changed

- Run activation trials in independent Codex CLI sessions with sub-agent delegation disabled.
  Use the caller's Codex login and configuration; no credentials are copied into the repo.
- Restrict forwarded process environment variables and make model calls opt-in; CI runs
  offline validators and mocked tests without a Codex login.
- Expand regression coverage for dataset validation, result parsing, security boundaries,
  links, and cross-platform installation.

### Fixed

- Harden skill-package validation and project-scoped skill linking against escaping paths,
  malformed metadata, linked ancestors, and partial mutation.
- Reject incompatible resume trials when skills, queries, CLI version, or runner options change;
  retain inconclusive-reason codes and avoid swallowing unexpected runtime exceptions.
- Count completed positive misses as false negatives, not infrastructure failures. Do not
  invent PR/ROC curves or AUC from binary skill-read observations.

---

## [v0.1.0] - Baseline on remote main

### Added

- Eight Python engineering skills covering domain modeling, callable/cache design,
  scikit-learn workflows, file-processing CLIs, Matplotlib configuration, Loguru, media
  processing, and binary buffers.
- Portable skill packages with progressive-disclosure references and Codex UI metadata;
  Linux/WSL and Windows project-scoped installation scripts.
- Initial package linting, routing evaluations, tests, GitHub Actions, security policy,
  and bilingual documentation.
