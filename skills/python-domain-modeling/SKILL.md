---
name: python-domain-modeling
description: Designs Python type annotations, domain objects, validation boundaries, dataclass/Pydantic models, invariants, interfaces, fixed choices, and object-copy semantics. Use when choosing ABC for owned nominal implementations versus Protocol for third-party structural compatibility, or when changing model behavior and boundary contracts. Never activate for dependency/version updates, translation, documentation-only edits, counting references, isolated syntax, or incidental modeling terms.
metadata:
  short-description: Choose Python models and interfaces while protecting boundaries and invariants
---

# Python Domain Modeling

## Activation

- **Keyword trigger:** the request substantively involves `typing.Any`, Protocol, ABC, Pydantic v2, `BaseModel`, `BaseSettings`, dataclass, Enum/Literal, domain models, invariants, `copy.copy`, `copy.deepcopy`, or alias preservation.
- **Intent trigger:** the user asks to design or review Python type interfaces, including ABC versus Protocol ownership, configuration models, input models, domain objects, or fixed choices.
- **Disclosure:** once when starting applicable work, briefly state: `Using $python-domain-modeling because this task involves ...`.
- **Exit:** stop applying this skill when the task no longer concerns Python model or interface decisions.
- **Do not trigger:** a term that appears only in a filename, dependency list, log, or unrelated context is insufficient.

---

## Start From the Data Lifecycle

Before choosing dataclass or Pydantic, trace one real use case:

1. Where does data enter from HTTP, configuration, messages, files, or third-party SDKs?
2. Which layer converts an untrusted representation into accepted program values?
3. Which rules are input-format constraints, and which are domain invariants that must hold throughout object lifetime?
4. Who mutates, serializes, persists, or exports the object?
5. Should an error be rejected at the boundary, converted into a domain error, or handled by the caller?

Read [references/decision-table.md](references/decision-table.md) for adjacent choices. Read [references/typing-interfaces.md](references/typing-interfaces.md), [references/pydantic-v2.md](references/pydantic-v2.md), [references/dataclass-guide.md](references/dataclass-guide.md), or [references/copy-semantics.md](references/copy-semantics.md) only when that area is relevant. Read [references/scenarios.md](references/scenarios.md) when multiple choices remain plausible.

---

## Separate Boundary Models From Domain Objects

- Parse external requests, configuration, and messages at boundaries. Pydantic may own parsing, coercion, field errors, and protocol compatibility; `pydantic-settings` may own configuration sources and precedence.
- Internal entities and value objects should express behavior and invariants. Do not introduce runtime validation merely to obtain type hints.
- When boundary and domain semantics differ, use an explicit converter or named factory. Do not hide differences in field names, units, defaults, or nullability behind unexplained dictionary unpacking.
- Reuse one model only when the external contract and internal concept truly share semantics, validation rules, serialization behavior, and change cadence.

---

## Distinguish Construction Rules From Lifetime Invariants

- Use generated dataclass initialization when fields can be assigned directly.
- Put construction-only cross-field validation, normalization, and derived-field calculation in `__post_init__`.
- Do not rely only on `__post_init__` for rules that must survive later state changes. Use named behavior methods, immutable objects, or a setter only when public assignment is appropriate.
- Use a read-only property for a value computed on access. Do not move construction logic into a property merely to keep `__init__` visually short.
- A property does not reduce per-instance memory. Evaluate `slots=True` when compact layout matters, and verify with measurement.
- Dataclass fields and same-named properties can conflict with generated initialization. Prefer `InitVar`, private storage, a named factory, or a regular class when input conversion is required.

---

## Choose Interfaces and Fixed Choices Deliberately

- Avoid `Any` when the value has a knowable shape. Prefer a concrete type, generic parameter, union, Protocol, TypedDict, or validated boundary model. Use `Any` deliberately at truly dynamic/untyped boundaries and narrow it promptly.
- Choose ABC or Protocol only after deciding whether nominal inheritance, shared implementation, runtime registration, or structural compatibility is required.
- Do not create an interface merely because two classes currently share method names. Identify the stable capability required by a caller.
- Choose Enum or Literal based on scope, reuse, serialization, and whether members require behavior.
- After introducing Enum, verify JSON, database, CLI, and log values so an internal member name does not accidentally become an external contract.

---

## Implementation and Verification

1. Write down the trust boundary and object responsibility before implementation.
2. Keep parsing, domain construction, and serialization conversion in identifiable locations.
3. Test at least one valid construction, one invalid state, and one mutation path for each lifetime invariant.
4. When replacing an existing model, check call signatures, exception types, serialization, equality, hashing, copying, and defaults.
5. Use the smallest combination of modeling tools that expresses the actual constraints.

When copying an object graph is part of a model change, define which outer/nested objects and aliases must be shared or reconstructed. Do not treat `deepcopy()` as "every object becomes new" or pickle as a generic deep-copy substitute.

---

## Required Output

Report only the items relevant to the requested change; do not impose a full review on a small task.

State:

1. where data crosses the trust boundary;
2. which rules are input constraints versus domain invariants;
3. which invariants are construction-only versus lifetime-long;
4. why the selected tool is preferable to adjacent choices;
5. where boundary, domain, and persistence conversions occur; and
6. which invalid states, mutations, and serialization contracts are tested.
