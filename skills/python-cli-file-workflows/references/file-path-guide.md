# File Streaming and Path Guide

## Streaming Patterns

Text lines:

```python
from collections.abc import Iterator
from pathlib import Path


def iter_lines(path: Path) -> Iterator[str]:
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            yield line.rstrip("\n")
```

Binary chunks:

```python
def iter_chunks(path: Path, chunk_size: int = 1024 * 1024):
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            yield chunk
```

Use `csv.reader`/`DictReader` directly over an open text stream. JSONL can be parsed one line at a time. A single large JSON document needs an incremental parser or different storage format. Compressed streams can still be incremental when opened through the relevant compression module.

Check the whole pipeline: `list(iterator)`, global sorting, full-data joins, and retaining all transformed records can reintroduce unbounded memory.

---

## Path Ownership

Source-adjacent configuration:

```python
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = MODULE_DIR / "config.toml"
```

Use this only when execution guarantees a real module file. `__file__` may be absent in interactive sessions and some embedded/generated execution contexts. Frozen/zip/package-resource layouts can also make direct sibling assumptions inappropriate.

Installed package resources:

```python
from importlib.resources import files

template = files("my_package.templates").joinpath("report.txt")
text = template.read_text(encoding="utf-8")
```

When an API requires a real filesystem path, use `importlib.resources.as_file()` for the required lifetime.

CLI arguments:

```python
input_path = args.input_file.expanduser()
```

Keep relative CLI paths relative to the caller's working directory unless the interface explicitly documents another base. Resolve/canonicalize only when needed for comparison, diagnostics, or security checks; `resolve()` also follows symlinks and can change intended path semantics.

Official references:

- <https://docs.python.org/3/library/pathlib.html>
- <https://docs.python.org/3/library/importlib.resources.html>
- <https://docs.python.org/3/library/fileinput.html>
