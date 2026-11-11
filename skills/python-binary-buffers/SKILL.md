---
name: python-binary-buffers
description: Designs and reviews executable Python binary parsing, bytes/bytearray ownership, memoryview lifetimes, zero-copy buffers, and chunked protocols. Use when changing or assessing runtime representation, parsing, or ownership. Never activate for translation, README/documentation-only edits, word counting, ordinary text encoding explanations, or incidental binary terms.
metadata:
  short-description: Design safe bytes, bytearray, memoryview, and binary-buffer boundaries
---

# Python Binary Buffers

## Activation

- **Keyword trigger:** the task substantively involves `bytes`, `bytearray`, `memoryview`, the buffer protocol, `struct`, binary protocols, byte order, encoding/decoding, zero-copy operations, buffers, or chunked I/O.
- **Intent trigger:** the user asks to systematically review Python binary reading, parsing, assembly, or transfer in files, networking, or protocols.
- **Disclosure:** once when starting applicable work, briefly state: `Using $python-binary-buffers because this task involves ...`.
- **Exit:** stop applying this skill when the task no longer concerns Python binary data.
- **Do not trigger:** a term found only in an unrelated log, filename, or dependency is insufficient.

---

## Define the Binary Contract First

Determine the source, whether data is mutable, who owns the underlying buffer, field lengths, byte order, encoding, lifetime, and whether zero-copy behavior is a measured requirement.

Read [references/buffer-guide.md](references/buffer-guide.md) for representation choices.

---

## Choose the Representation

- `bytes` represents an immutable byte sequence and is suitable for stable messages, hash inputs, and hashable values.
- `bytearray` represents a mutable Python-owned contiguous byte buffer for in-place assembly or editing.
- `memoryview` is a non-owning view over a buffer-protocol object. Use it to slice, parse, or pass data without unnecessary copies.
- Convert text at explicit boundaries with `encode` and `decode`; do not rely on an implicit default encoding for protocols or persistence.

---

## Make Ownership and Lifetime Explicit

- A memoryview remains valid only while its exporter remains valid. Do not return a view into a resource that is about to close, release, resize, or be reused.
- For shared mutable buffers, define who may write, when mutation is allowed, and whether concurrent access is safe.
- Create an independent `bytes` snapshot when data must outlive or detach from the original owner.
- Know which slices copy: bytes and bytearray slices usually allocate; memoryview slices usually remain views.

---

## Parse and Write Defensively

- Specify byte order, field width, signedness, alignment, and length limits.
- Check remaining length before reading a field so truncation becomes a clear protocol error.
- Bound untrusted length fields to prevent excessive allocation or indefinite waiting.
- Keep `struct` formats and `int.from_bytes`/`to_bytes` calls traceable to the protocol definition.
- Process large files and streams incrementally rather than reading everything by default.

---

## Verify Performance Claims

Zero-copy is not a default goal. Measure allocation, peak memory, copy cost, lifetime complexity, and end-to-end throughput. Confirm that downstream C extensions, NumPy, or I/O APIs actually accept the buffer protocol without making their own copy.

---

## Required Output

Report only the items relevant to the requested change; do not impose a full review on a small task.

State the binary format; representation; ownership and mutability; copy versus view boundaries; byte order, length, and encoding; truncation and malicious-input handling; and performance evidence.
