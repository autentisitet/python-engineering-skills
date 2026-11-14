# Skill Evals

`train_queries.json` and `validation_queries.json` are the stable routing-evaluation split. Each
file is a self-describing object:

```json
{
  "version": 1,
  "split": "train",
  "split_seed": 20261112,
  "queries": [
    {
      "id": "python-loguru-logging-positive-03",
      "skill": "python-loguru-logging",
      "category": "direct",
      "query": "Configure Loguru file rotation, retention, compression, and disk-budget tests.",
      "should_trigger": true
    }
  ]
}
```

`version` and `split_seed` identify the dataset format and split definition; change them only
through a deliberate schema or split revision.

The GitHub Actions workflow runs the offline validators and mocked unit tests only. It does not
install Codex, call `make eval`, or need a Codex profile, login, or API key. Discovery and
model-backed activation are explicit local steps below.

## Categories

Every query carries a `category` that describes how the request relates to the target skill:

| Category | Meaning |
| --- | --- |
| `direct` | Names the skill's concrete API, tool, or artifact. A keyword match alone could route it. |
| `indirect` | A problem scenario inside the skill's domain without naming that API. Routing requires recognizing the underlying need. |
| `embedded` | The skill is one component of a larger, multi-part task. |
| `boundary` | A negative case in an adjacent domain that shares surface keywords but must not trigger the skill. |

Positive cases use `direct`, `indirect`, or `embedded`; negative cases use `boundary`.

---

## Offline Validation

```bash
python3 -m scripts.evals.validate_evals
```

This checks the envelope (`version`, `split`, `split_seed`), per-query fields and categories,
registered skill names, duplicate ids and queries, positive/negative coverage per skill per split,
and the fixed id numbering. It does not call a model.

---

## CSV Review

Every JSON query set has a sibling CSV (`train_queries.csv`, `validation_queries.csv`) for editing
or review in Excel. Columns are `id,skill,category,query,should_trigger`; the file carries a UTF-8
BOM so Excel opens it correctly.

```bash
# JSON -> CSV
make queries-csv
# edited CSV -> JSON
make queries-json
# review digests (not committed)
make queries-checksum
```

The conversion commands are:

```bash
python3 -m scripts.evals.convert_queries to-csv \
  evals/train_queries.json evals/train_queries.csv
python3 -m scripts.evals.convert_queries to-json \
  evals/train_queries.csv evals/train_queries.json \
  --split train --split-seed 20261112
```

`to-json` writes to a temporary file and only replaces the target JSON when its sha256 changes, so
running the command with an unchanged CSV is a no-op.
Formula-like cells and leading apostrophes are escaped on export and restored on import so Excel
does not evaluate query text as a formula.

---

## Discovery and Activation

```bash
python3 -m scripts.evals.check_skill_discovery \
  --output evals/results/discovery.json
python3 -m scripts.evals.run_activation_evals evals/train_queries.json \
  --allow-model-calls \
  --reasoning-effort low \
  --output evals/results/activation-train.json
```

| Step | Behavior |
| --- | --- |
| Discovery | Checks repository-scope skill loading in an empty temporary Codex home; no model call or login. |
| Activation | Starts one fresh `codex exec --ephemeral` process per trial, not a sub-agent of the caller's session. Disables sub-agents and bundled skills, and uses read-only access. |
| Authentication | Uses the caller's Codex config and CLI login; no login file is copied into this repository. Explicitly permitted environment variables may also be forwarded. |
| Security boundary | CLI and tool environments are restricted, but read-only does not prevent host file reads. User config may start integrations; use trusted queries or external isolation. Queries and tool output may reach the model provider. |
| Evidence | Stops early when a successful file-reading command emits the target `SKILL.md` markers. This is command/output evidence, not OS-level proof of a read. |
| Failure and resume | The first trial preflights the run; hard process failures stop later calls. Timeouts and missing completion are inconclusive. `--resume` reuses trials only when Codex version, skills hash, options, and each query's case hash match. |

The default timeout is 300 seconds per trial. Use `--model` and `--reasoning-effort low` to
control costs; `--help` lists the remaining options. Configure providers in Codex itself.
Export edited CSVs to JSON before evaluation; `make validate` checks their agreement.

| Saved field | How it is computed |
| --- | --- |
| `dataset_sha256` | SHA-256 of the input JSON file's bytes. |
| `skills_sha256` | SHA-256 of sorted skill-relative paths and file contents. |
| `case_sha256` | SHA-256 of canonical ID, skill, category, label, and query text. |
| `codex_options` / `codex_version` | Runner policy and CLI version when recorded, used for resume compatibility. |

Results live in ignored `evals/results/`. `make queries-checksum` prints JSON/CSV digests but
does not save them. For subset results, freshness compares selected case hashes to the current
split; unknown IDs or missing hashes yield unknown freshness. Resume cannot detect changes to
the caller's Codex config or login: start a new result file after either changes.

The README's charts and metrics use `activation-train.json` and
`activation-validation.json`. Their dataset, all 176 case, and skill digests match this tree.
Those files omit `dataset_split` (so the summarizer reports `dataset=unknown`) and the CLI
version. No additional model calls were made to recreate the charts.

### Retrying timeouts

Extract a retry dataset from an activation result and the source query set:

```bash
python3 -m scripts.evals.extract_retry_cases \
  --result evals/results/activation-validation.json \
  --dataset evals/validation_queries.json \
  --output evals/results/validation-timeout-retry.json
```

Only inconclusive trials with `reason == "timeout"` are selected by default; use
`--any-inconclusive` to include every inconclusive trial. `make retry-dataset` is a shortcut for
the validation split.

### Cross-checking with a different model

Re-run baseline error cases under another model and report which errors disappear. First run the
current validation JSON to create a baseline under known runtime conditions:

```bash
python3 -m scripts.evals.run_activation_evals evals/validation_queries.json \
  --model deepseek-flash --reasoning-effort low --allow-model-calls \
  --output evals/results/activation-validation-current.json
python3 -m scripts.evals.cross_check_evals \
  --baseline evals/results/activation-validation-current.json \
  --dataset evals/validation_queries.json \
  --model deepseek-v4-pro --reasoning-effort low \
  --allow-model-calls \
  --output evals/results/activation-validation-v4pro.json
```

The model is never hardcoded: pass `--model` (or `--profile`). By default only the baseline
routing-error cases (`fail` plus positive misses without an infrastructure failure) are re-run;
`--all-cases` runs the full dataset and also detects newly introduced errors. `--json` prints the
`resolved/persisted/unresolved/introduced` buckets. A changed query under the same ID is rejected
before model calls; older results without case hashes require an exact full-dataset SHA match.
The shortcut is
`make cross-check CROSS_MODEL=deepseek-v4-pro`.

---

## Artifact Quality

Routing scores measure skill reads, not artifact correctness. There is no model-backed quality
baseline yet. For each sample:

1. Follow the [acceptance samples](artifact-acceptance-samples.md) and their
   [temporary-directory workflow](artifact-acceptance-samples.md#isolated-working-directory).
   Prompts explicitly invoke a skill, so they do not test automatic routing.
2. Review the actual output and checks. A skill read alone is not a quality pass. Keep raw logs
   and working files in the temporary project or ignored `evals/results/`.
3. Copy [the report template](artifact-reviews/TEMPLATE.md) to
   `evals/artifact-reviews/YYYY-MM-DD-model.md`. For each attempted sample, record fixture,
   model/CLI/skill revisions, verdict, reason, and evidence links under
   `evals/artifact-reviews/<run-id>/`; leave missing samples as `not-run`.
4. Publish only human-reviewed, scrubbed evidence. Do not report an aggregate quality score for
   unreviewed samples. Inspect relative links, staged content, and push destination:

```bash
git add evals/artifact-reviews/YYYY-MM-DD-model.md evals/artifact-reviews/<run-id>/
git diff --cached --check
git diff --cached -- evals/artifact-reviews/
git remote get-url --push origin
# After reviewing the destination and staged content:
git commit -m "docs: publish reviewed skill artifact samples"
git push origin HEAD
```

The placeholders above represent files created only after an actual review. The repository does
not yet contain an evaluated artifact report, and running routing evals does not create one.

---

## Metrics and statistical calibers

Every trial is one independent `codex exec --ephemeral` turn. For a positive case the target
skill should be read; for a negative case it should not.

| Cell | Definition |
| --- | --- |
| TP | positive case, skill read observed (`pass`) |
| FN | positive case with a completed turn and no skill read (`fail`), or a positive `inconclusive` without an infrastructure failure |
| FP | negative case where the skill was read (`fail`) |
| TN | negative case where the skill was not read (`pass`) |
| Inconclusive | infrastructure failure (`timeout`, `agent_process_failed`, `completion_event_missing`, `evaluation_unavailable`) |

Derived rates are rounded to 4 decimal places:

$$
\begin{aligned}
P &= \frac{TP}{TP+FP} \\
R &= \frac{TP}{TP+FN} \\
\mathrm{Specificity} &= \frac{TN}{TN+FP} \\
\mathrm{FPR} &= \frac{FP}{FP+TN} \\
\mathrm{FNR} &= \frac{FN}{FN+TP} \\
\mathrm{Accuracy} &= \frac{TP+TN}{TP+FN+FP+TN} \\
\mathrm{BalancedAccuracy} &= \frac{R+\mathrm{Specificity}}{2} \\
F_1 &= \frac{2PR}{P+R} \\
\mathrm{InconclusiveRate} &= \frac{N_{\mathrm{inconclusive}}}{N_{\mathrm{total}}} \\
\mathrm{Coverage} &= \frac{TP+FN+FP+TN}{N_{\mathrm{total}}}
\end{aligned}
$$

| Dimension | Interpretation |
| --- | --- |
| Routing | Inconclusive trials do not enter the classification denominators; zero denominators produce `null` in JSON. Results are also grouped by skill and query category. |
| Query stability | Trigger rate is `loaded_trials / valid_trials`; query coverage is `valid_trials / total_trials`. Neither is a calibrated confidence score, so PR/ROC curves and AUC cannot be inferred. |
| Infrastructure | Inconclusive rate and failure reasons describe execution health. Duration uses wall-clock time per trial (mean, min, max, P50, P95); train/validation gaps require split-aware results. |
| Usage | Only completed turns report input, cached-input, and output tokens. Cached input is already part of input, not added again to `total_tokens`. `tokens_per_second` divides input plus output tokens by duration across usage-bearing trials; early stops make these totals a lower bound. |

---

## Summarize and Plot

```bash
python3 -m scripts.evals.summarize_evals evals/results/activation-train.json
uv run python -m scripts.evals.plot_evals \
  evals/results/activation-train.json evals/results/activation-validation.json \
  --output-dir evals/results
```

Charts are optional diagnostics. The root README publishes only skill-routing charts:

| Chart | Contents |
| --- | --- |
| `routing-radar.png` | Per-skill precision, recall, and F1; overlays train/validation when both are supplied. |
| `routing-confusion.png` | Side-by-side train/validation matrices when both are supplied; counts remain separate. |
| `routing-train-validation-per-skill.png` | Per-skill P/R/F1, sample counts, FP/FN, and denominators. |

Legacy results without split metadata are matched by dataset SHA-256. Trend charts require
repeated runs of the **same** split, dataset, CLI version, and model options; train versus
validation is not an iteration trend. Undefined rates show N/A. With fewer than three skills,
radar charts show an empty state. Early-stopped trials lack usage, so token totals cannot serve
as full cost estimates.

| Local output | Keep or clean up |
| --- | --- |
| `assets/evals/` images linked by the root READMEs | Keep: these are the historical visualizations intended for Git. |
| Ignored `routing-latency.png`, `routing-overall.png`, `routing-trend.png` | Optional diagnostics; safe to delete when no longer needed. |
| `evals/results/activation-train.json`, `activation-validation.json` | Keep locally to audit the historical metrics; these raw results are ignored by Git. |
| Old `evals/results/routing-full-*.png`, `routing-summary.json`, smoke/discovery outputs | Disposable local artifacts; rerun the relevant command when needed. |
