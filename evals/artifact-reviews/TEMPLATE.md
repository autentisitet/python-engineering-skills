# Artifact Review: TEMPLATE (not a result)

Copy this file to `evals/artifact-reviews/YYYY-MM-DD-model.md` for one evaluated snapshot. Keep
private raw logs under `evals/results/`; only publish reviewed and scrubbed evidence. The task
definitions are in [artifact acceptance samples](../artifact-samples.md). This file is
a template and contains **no measured quality results**.

## Conditions

| Field | Record for this run |
| --- | --- |
| Date and reviewer | Pending |
| Model and provider | Pending; record the actual model, not only a profile alias |
| Codex CLI version | Pending (`codex --version`) |
| Skill digest and source revision | Pending (SHA-256 and Git commit / working-tree state) |
| Fixture revision | Pending (digest or snapshot of the temporary project before agent edits) |
| Session setup | Pending (system temporary path, copied skill, fresh session, explicit `$skill`, other relevant options) |
| Review method | Manual checks against the actual artifact and verification output |

Explicit invocation tests work *after* selecting a skill; it does not measure whether a skill
would have been selected without prompting. Record any failed or unavailable setup separately.

---

## Results

`not-run` is not a pass. Use `pass`, `fail`, or `inconclusive` only after recording the evidence
below; do not publish an aggregate quality score from a partial run. Leave the activation
Precision/Recall/F1 results unchanged.

| Sample / skill | Verdict | Reviewed artifact and evidence |
| --- | --- | --- |
| Binary Buffers / `python-binary-buffers` | not-run | Pending |
| Callable and Cache Lifetime / `python-callable-caching` | not-run | Pending |
| File Processing CLI / `python-cli-file-workflows` | not-run | Pending |
| Domain Modeling / `python-domain-modeling` | not-run | Pending |
| Loguru Shutdown / `python-loguru-logging` | not-run | Pending |
| Matplotlib Configuration / `python-matplotlib-config` | not-run | Pending |
| Media Processing / `python-media-processing` | not-run | Pending |
| Scikit-Learn Workflow / `python-sklearn-workflow` | not-run | Pending |

---

## Sample Records

Add one entry per run sample, including failures and inconclusive attempts. Replace the bracketed
fields; keep evidence under `evals/artifact-reviews/<run-id>/` with relative links from this report.

### [Sample / Skill]

- Fixture and exact prompt: [fixture revision and prompt as run, or link to an unchanged sample].
- Result: [pass / fail / inconclusive]; target skill read: [yes / no / unknown].
- Artifact: [link to reviewed, scrubbed patch or output; mark any redactions].
- Checks: [each applicable acceptance condition, its observed evidence, and failure reason].
- Verification: [command, exit status, and relevant test output or visual inspection].
- Workspace check: [confirm the session and tests ran in the temporary project, not this repository].
- Reviewer conclusion: [why the actual artifact satisfies or fails the conditions].

---

## Publication Check

Before committing, confirm the report's claims match the actual artifacts. Remove credentials,
tokens, raw session logs, private user data, and sensitive paths; if evidence cannot be published,
state the limitation instead of claiming an independently verifiable pass. Check all relative
links, including sample and artifact links. Do not conflate a skill read or passing unit tests
with the broader claim that the skill improved performance without a no-skill control.
