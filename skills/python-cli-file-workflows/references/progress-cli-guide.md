# tqdm and argparse Guide

## Contents

- tqdm iterable and manual progress patterns
- Stable messages and nested progress bars
- argparse construction and argument options

---

## tqdm

Natural iterable:

```python
from tqdm import tqdm

for path in tqdm(
    paths,
    desc="Process files",
    total=len(paths),
    unit="file",
    leave=False,
):
    ...
```

Omit `total` when tqdm can obtain a reliable length. Use `unit="line"`, `"file"`, `"batch"`, or another real work unit. `leave=False` is useful for transient inner bars; retaining the final outer summary is often more readable.

Manual/non-iterable progress:

```python
with tqdm(total=expected_bytes, unit="B", unit_scale=True) as progress:
    while chunk := source.read(chunk_size):
        process(chunk)
        progress.update(len(chunk))
```

Manual `update()` is correct here; the context manager guarantees close/cleanup. Update by the completed delta, not the absolute count.

For messages during progress:

```python
tqdm.write(f"Skipped invalid file: {path}")
```

Nested bars need distinct `position` values when automatic positioning is insufficient. Avoid nested bars when a postfix or one aggregate bar communicates the work more clearly. For concurrent workers, coordinate tqdm locking/output or aggregate progress in the parent process.

---

## argparse

```python
import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Process input records without loading the full file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("input_file", type=Path, help="Input JSONL file")
    parser.add_argument(
        "--output-file",
        type=Path,
        required=True,
        help="Destination file",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Records processed per batch",
    )
    parser.add_argument(
        "--mode",
        choices=("strict", "skip-invalid"),
        default="strict",
        help="Invalid-record policy",
    )
    parser.add_argument(
        "--verbose",
        action="count",
        default=0,
        help="Increase diagnostic verbosity",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0",
    )
    return parser
```

Selection rules:

- `type`: conversion/validation appropriate for one token; use a custom callable for bounded positive integers when needed.
- `default`: meaningful behavior that is visible in help when useful; avoid mutable defaults.
- `required`: only for optional arguments that truly must be named.
- `action`: flags, counts, append behavior, constants, or version/help behavior.
- `choices`: small closed sets; avoid huge/dynamic lists that produce poor help.
- `help`: user-visible meaning, units, defaults, and constraints.
- `dest`: explicit Python attribute only when the automatic hyphen-to-underscore mapping is not right.

Constructor options are not a checklist:

- `description` is commonly useful; `epilog` is useful for examples or further guidance.
- Leave `prog` and generated `usage` alone unless invocation is intentionally presented differently.
- Use `formatter_class` when defaults or carefully formatted examples improve help.
- Use `parents` only for genuinely shared, fully initialized argument sets, usually with `add_help=False` on the parent.
- Keep `prefix_chars="-"` for conventional CLIs.
- Keep conflict errors unless compatibility requires deliberate override behavior.

Official references:

- <https://docs.python.org/3/library/argparse.html>
- <https://tqdm.github.io/docs/tqdm/>
