# Artifact Acceptance Samples

These are eight small **artifact behavior** checks, one per skill. They are not routing queries.
They have not been run successfully against a model, and their outcomes must not be included in
the historical activation Precision, Recall, or F1 scores. Run them only in a new fixture under
the system temporary directory, never in this repository or a working-tree copy of it. Do not
put credentials in fixtures or grant remote write access.

Each prompt explicitly invokes its target skill with `$skill-name`, so these samples test the
work produced **after** activation, not whether the agent routes to the skill unprompted. Use
the prompt verbatim in a fresh session with the named skill installed. Save the complete
prompt and resulting artifact separately from routing results. For each attempt, record the model,
Codex version, skill-content SHA-256, fixture revision, observed skill read (if available),
verification commands and output, and a pass/fail/inconclusive reason. Reading a skill is not a
quality pass. Review generated code before running it; execute only in a disposable environment.

## Isolated Working Directory

On Linux/WSL, start in this repository and create a fresh temporary project for **each** sample:

```bash
repo="$PWD"
skill=python-binary-buffers  # Replace with the sample's skill name.
fixture="$(mktemp -d /tmp/skill-artifact.XXXXXXXX)"
mkdir -p "$fixture/.agents/skills"
cp -R "$repo/skills/$skill" "$fixture/.agents/skills/$skill"
test -z "$(find "$fixture/.agents/skills/$skill" -type l -print -quit)"
git -C "$fixture" init -q
cd "$fixture"
```

Create only the files described by that sample's Fixture paragraph **inside** `$fixture`. Start
a fresh Codex session with `$fixture` as its working directory, verify that the installed skill
resolves to `$fixture/.agents/skills/$skill/SKILL.md`, and submit the sample's prompt verbatim.
Never point the session at the original repository, copy its entire working tree, or link the
skill back to the repository. Inspect the copied package for symlinks before running; reject a
sample if a link would escape the fixture. On other platforms use the OS temporary directory
and the same copy-only layout. This controls where the task writes; it does **not** prevent a
session with host filesystem access, user configuration, hooks, or MCP integrations from reading
outside the fixture. Use an external sandbox for untrusted fixtures.

Run the sample's tests from the temporary project. Keep raw logs and unreviewed output outside
the tracked repository; after manual review, copy only scrubbed evidence into
`evals/artifact-reviews/<run-id>/` and fill in the report template. Record the temporary fixture's
content digest or snapshot before the agent edits it. Do not delete the temporary project until
the artifact and evidence have been reviewed; remove it when no longer needed.

---

## Binary Buffers

Skill: `python-binary-buffers`.

Fixture: a fresh Python project with `decoder.py` and `tests/test_decoder.py`; no third-party
packages. Frames have a two-byte unsigned big-endian payload length followed by that many bytes.
The reference bytes are `b"\x00\x03abc\x00\x00"`. Include a truncated one-byte header and a
declared payload longer than the available data as negative inputs.

Prompt: "Use $python-binary-buffers. Implement `decode_frames(data: bytes) -> list[bytes]` for
this length-prefixed protocol.
Keep input ownership clear. Add focused tests for consecutive frames, an empty payload, and both
truncated cases. Show the patch and the test result."

Pass only if the function returns `[b"abc", b""]` for the reference bytes, rejects both
truncated inputs with `ValueError` instead of silently accepting a partial frame, and its tests
exercise those cases. Run `python3 -m unittest discover -s tests` in the fixture. Fail if the
answer only explains the protocol without implementing and testing it, or mistakes the payload
length for a total frame length.

---

## Callable And Cache Lifetime

Skill: `python-callable-caching`.

Fixture: a Python project containing a `UserDirectory` that calls a supplied `lookup(user_id)`
function and a test file with two directories backed by different lookup functions. Include a
lookup returning `None` and an update to a previously cached user.

Prompt: "Use $python-callable-caching. Add per-instance lookup caching and
`invalidate(user_id)` to `UserDirectory`. Cache valid
`None` results, avoid sharing cached values across directories, and test reuse, invalidation, and
instance separation. Show the patch and test result."

Pass only if repeated lookups, including `None`, call the backing function once until invalidated;
invalidating one ID leaves other entries alone; and independent instances never share a cache.
Check the call counters in `python3 -m unittest discover -s tests`. Fail if it uses a class-level
cache, confuses a cache miss with cached `None`, or only describes the intended behavior.

---

## File Processing CLI

Skill: `python-cli-file-workflows`.

Fixture: a Python project with a text file containing two matching lines and one nonmatching
line, a `tests/` directory, and an empty `count_lines.py`. Include a test invoking the CLI from
a working directory different from the script's directory.

Prompt: "Use $python-cli-file-workflows. Implement a CLI that counts lines containing a
user-supplied substring in a file too
large to load into memory. Resolve relative input paths from the current working directory.
Add a test for the count and path behavior; show the patch and test result."

Pass only if the CLI iterates over the file rather than using `read()`/`readlines()`, reports the
expected count of two, uses `argparse`, and handles relative paths from the caller's working
directory. Run `python3 -m unittest discover -s tests`. Fail if it materializes the full input,
silently resolves relative to `__file__`, or only prints a proposed implementation.

---

## Domain Modeling

Skill: `python-domain-modeling`.

Fixture: a Python project with an untrusted request payload containing an order ID and quantity,
plus tests for a positive quantity, zero, and assignment to an existing order. Choose either a
validated immutable domain object or a mutable object that enforces its invariant on mutation.

Prompt: "Use $python-domain-modeling. Separate untrusted request parsing from the domain `Order`.
Reject nonpositive
quantities at the boundary and ensure `Order` cannot retain one later. Make conversion explicit,
add tests for construction and mutation, and show the patch and test result."

Pass only if the request is checked before conversion, the domain invariant survives construction
and subsequent attempts to mutate quantity, and tests reject zero. Run
`python3 -m unittest discover -s tests`. Fail if `__post_init__` is the only protection for a
mutable public field, or if request and domain objects are treated as the same trust boundary.

---

## Loguru Shutdown

Skill: `python-loguru-logging`.

Fixture: a small async application using Loguru with a temporary log directory and an exception
path. Its tests can patch the logger to observe call order without writing large log files.

Prompt: "Use $python-loguru-logging. Configure a Loguru file sink with 10 MB rotation, seven-day
retention, and `enqueue=True`.
Log the exception with its traceback and finish queued logging before the event loop exits. Add
a focused test for shutdown ordering; show the patch and test result."

Pass only if the sink options are set, exception logging preserves the traceback, and the queued
sink is completed before loop shutdown. Check both the test and the emitted fixture log. Fail if
it logs only `str(exc)`, forgets to await shutdown completion, or logs fixture credentials.

---

## Matplotlib Configuration

Skill: `python-matplotlib-config`.

Fixture: a small plotting module and tests that run with the Agg backend. Inputs contain Chinese
category labels; the fixture should list available fonts, not assume a particular CJK font is
installed. Include a figure-output path in a disposable directory.

Prompt: "Use $python-matplotlib-config. Implement `plot_counts(labels, counts)` returning a
Matplotlib Figure. Apply one style
before creating the figure, set up CJK-capable font fallbacks, and configure bars and labels via
Axes methods. Add an Agg rendering test; show the patch and result."

Pass only if the function returns a Figure, style order is correct, Axes methods configure the
plot, and an Agg render produces a nonempty image. Inspect Chinese glyphs visually on a machine
with one of the configured fonts; otherwise mark that check inconclusive, not passed. Fail if it
mixes competing global theme mechanisms or claims an uninstalled font renders correctly.

---

## Media Processing

Skill: `python-media-processing`.

Fixture: a short, locally generated variable-frame-rate video with known, irregular frame
timestamps, and a requested timestamp beyond EOF. Use a disposable directory; the test machine
must have PyAV and the video fixture available before running this sample.

Prompt: "Use $python-media-processing. Implement bounded-memory sampling of one RGB frame for
each requested timestamp using
PyAV. Choose frames using decoded timestamps, define behavior beyond EOF, close the container,
and add a test against this variable-frame-rate fixture. Show the patch and test result."

Pass only if selection uses decoded `pts`/`time_base` (or equivalent), frames are processed
incrementally, RGB conversion and EOF behavior match the tests, and the container closes on
success and error. Fail if selection uses frame number divided by an assumed FPS, resources leak,
or no actual variable-timestamp test runs. If PyAV or the fixture is unavailable, record
inconclusive rather than pass.

---

## Scikit-Learn Workflow

Skill: `python-sklearn-workflow`.

Fixture: a binary classification dataset with numeric features and at least four patients,
multiple rows per patient, known binary labels, and `scikit-learn` installed. Include a test that
checks patient groups do not overlap across every fold.

Prompt: "Use $python-sklearn-workflow. Evaluate a classifier with patient-grouped
cross-validation and F1 scoring. Put feature
scaling inside the estimator Pipeline, verify patient disjointness in every fold, and add a test.
Show the patch and test result."

Pass only if the splitter receives patient groups, training and validation patients are disjoint
in every fold, scaling fits only inside each fold, and F1 is computed from held-out predictions.
Run the fixture's tests and inspect the split assertion. Fail if preprocessing runs before CV,
groups are ignored, or training-set scores are reported as validation quality.

---

## Recording Outcomes

Keep the full artifact and evidence outside the routing results. For each sample, record the
following fields; do not fill them in until an actual run and review:

| Field | Record |
| --- | --- |
| Sample and fixture revision | Which sample and exact input snapshot were used |
| Model, Codex version, skill SHA-256 | The conditions under which the artifact was produced |
| Prompt, artifact, skill read | The verbatim request, actual output, and separate activation observation |
| Verification and verdict | Commands/output checked, pass/fail/inconclusive, and a reason |

One passing sample supports only that task under that model and fixture. It neither establishes
a general skill-quality score nor shows that the skill caused the improvement; causal claims need
an equivalent no-skill control and blinded comparison.
