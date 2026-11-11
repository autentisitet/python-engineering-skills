# Typing and Interface Guide

## Any

`Any` disables most static checking for operations flowing through it. Use it only when the value is genuinely dynamic or comes from an untyped boundary that cannot yet be modeled. Narrow promptly through validation, a type guard, Protocol, TypedDict, or a concrete model.

Do not replace `Any` mechanically with `object`: `object` accepts every value but requires type narrowing before use, which is often the safer contract.

---

## ABC and Protocol

| Need | Prefer |
| --- | --- |
| Owned implementations must explicitly declare the relationship | `ABC` |
| Shared implementation/template methods/registration | `ABC` or composition |
| Third-party objects cannot change inheritance | `Protocol` |
| Structural flexibility but owned implementations should be discoverable | Explicitly inherit the Protocol |

Protocols are primarily static structural contracts. Runtime-checkable protocols only check limited attribute presence and do not validate signatures or semantics. Structural matching can make implementation relationships harder to discover during debugging, so keep Protocols minimal and located near their consumers.

---

## Literal and Enum

- Use `Literal` for a few local values in one or a small number of signatures.
- Use `Enum`/`StrEnum` when choices are shared, iterated, parsed, labeled, serialized, or need behavior.
- Test external values explicitly. Internal Enum member names should not accidentally become database/API/CLI contracts.

Official references:

- <https://docs.python.org/3/library/typing.html>
- <https://docs.python.org/3/library/abc.html>
- <https://docs.python.org/3/library/enum.html>
