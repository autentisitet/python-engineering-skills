---
name: python-cli-file-workflows
description: Builds and reviews bounded-memory Python file-processing CLIs with explicit path bases, argparse contracts, and iterable- or callback-driven tqdm progress. Use when file scale, path ownership, progress semantics, or CLI behavior needs design. Never activate for tiny fixed fixtures that can be read wholly, swapping an already-chosen progress library, translation, documentation-only edits, dependency updates, web APIs, GUIs, shell-only scripts, or incidental Path/tqdm/argparse terms.
metadata:
  short-description: Build streaming Python file CLIs with clear progress and paths
---

# Python CLI File Workflows

## Activation

- **Keyword trigger:** the task substantively involves large files, line/chunk streaming, `Path(__file__)`, `importlib.resources`, iterable or callback-driven tqdm progress, nested progress bars, or argparse CLI design.
- **Intent trigger:** the user asks to implement or review a Python file-processing command with bounded memory, predictable paths, useful progress output, and a stable command-line interface.
- **Disclosure:** once when starting applicable work, briefly state: `Using $python-cli-file-workflows because this task involves a Python file-processing CLI.`
- **Exit:** stop applying this skill when I/O memory, path ownership, progress, and CLI arguments are settled.
- **Do not trigger:** an isolated `Path` expression, reading a known-small fixture in one call, replacing tqdm with another display library in an already-designed CLI, an ordinary library function, notebook-only task, or non-Python command is insufficient.

---

## Stream Inputs When the Format Allows It

- Iterate text files line by line instead of using `read_text()` or `read()` when the entire content is not needed:

  ```python
  with path.open("r", encoding="utf-8") as stream:
      for line in stream:
          ...
  ```

- Stream binary files in bounded chunks. Use format-aware incremental readers for CSV, JSONL, compressed streams, and record formats.
- Do not pretend every format is streamable with a line loop. A single JSON array may require an incremental parser or a producer-side change to JSONL.
- Accumulating every processed result in a list still defeats streaming. Write, aggregate, batch, or yield incrementally.
- Keep error policy explicit: fail-fast, skip with diagnostics, quarantine, or emit partial output.

Read [references/file-path-guide.md](references/file-path-guide.md) for paths, package resources, and streaming limits.

---

## Choose the Correct Path Anchor

- User-supplied relative paths normally resolve from the current working directory because that is the CLI contract users can control.
- For files deliberately shipped next to a source script/module, use `Path(__file__).resolve().parent` only when `__file__` exists in the target execution mode.
- For installed package data, prefer `importlib.resources`; package resources may not be ordinary filesystem files.
- Do not silently reinterpret every relative argument as script-relative. If configuration supports multiple bases, expose or document the rule.
- Avoid using `Path.cwd()` as a substitute for source location and avoid `__file__` in interactive/notebook contexts without a fallback or explicit parameter.

---

## Keep tqdm Output Stable

- Wrap an iterable directly when each iteration represents one unit of progress.
- For callbacks, bytes, batches, or work without a natural iterable, use `with tqdm(total=...) as progress:` and call `progress.update(completed_delta)`.
- Use `tqdm.write(...)` for messages while bars are active so output does not overwrite the display.
- Add `desc`, `total`, `unit`, and `leave` only when they improve interpretation. Do not claim an inaccurate total.
- Use nested bars only when outer and inner progress answer distinct questions. Set stable `position`/`leave` behavior and avoid deeply nested or highly concurrent terminal bars.

Read [references/progress-cli-guide.md](references/progress-cli-guide.md) for tqdm and argparse choices.

---

## Design argparse as a Public Interface

- Long CLI options use hyphens, such as `--input-file`; argparse normally exposes them as underscore attributes such as `args.input_file`.
- Use `dest` only when the default conversion is unsuitable or compatibility requires a stable attribute name.
- Give every user-facing argument useful `help`; add `type`, `choices`, `action`, `default`, or `required` only when they express the contract.
- Prefer positional arguments for essential operands and optional flags for modes/configuration. Required optional flags can be appropriate, but do not use them merely to imitate positional arguments.
- Add `action="version", version=...` for a real version flag. `version` is not a general standalone `add_argument()` keyword.
- `ArgumentParser` defaults for `prog`, generated `usage`, `prefix_chars="-"`, and conflict errors are usually correct. Customize `usage`, `parents`, `prefix_chars`, `conflict_handler`, or formatter only for a demonstrated interface need.
- Parse arguments in `main()` and keep processing logic callable/testable without mutating `sys.argv`.

---

## Required Output

State the streaming unit and memory bound; path anchor for user input versus packaged resources; progress total/unit/message behavior; nested-bar rationale if any; argument names, Python destinations, validation/default semantics; and tests for large input, path independence, help/errors, and interrupted processing.
