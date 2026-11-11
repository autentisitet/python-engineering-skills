# Python Modeling Decision Table

Use this table after identifying data sources, ownership, lifetime, and failure behavior.

## Object Representation

| Primary need | Usual choice | Confirm before choosing |
| --- | --- | --- |
| Small state with substantial behavior | Regular class | Whether construction or mutation requires explicit control |
| Field-oriented internal value object | `dataclass` | Equality, mutability, hashing, and copy semantics |
| HTTP, configuration, or other untrusted input | Pydantic `BaseModel` | Whether parsing, coercion, and field errors belong at this boundary |
| Environment and layered application configuration | `pydantic-settings` `BaseSettings` | Source precedence, casing, nesting, and secret boundaries |
| Dataclass API plus runtime parsing | `pydantic.dataclasses.dataclass` | Whether compatibility is real and its validation/copy behavior is understood |
| Large numbers of lightweight records | `NamedTuple`, slotted dataclass, or specialized structure | Mutability, access pattern, and measured memory behavior |
| Multiple complex construction sources | Regular class with named factories | Keep protocol parsing, I/O, and domain construction out of one constructor |

Pydantic is useful at boundaries; this does not imply that a Pydantic object should flow through application, domain, and persistence layers. Reuse depends on shared semantics and change cadence, not on reducing class count.

---

## Boundary Conversion

| Situation | Usual approach |
| --- | --- |
| API and domain fields have identical semantics | Explicit factory or small conversion function |
| Names match but units, defaults, or nullability differ | Field-by-field conversion; avoid unexplained `**model_dump()` |
| Creation requires external queries | Application service or factory object coordinates dependencies |
| Stored historical nulls are invalid for new objects | Repository adapter migrates or rejects with an observable error |
| External protocol must accept legacy fields | Compatibility remains at the boundary; internal code sees one meaning |

Place conversion near the boundary where semantics change. Do not create a global `utils.py` that absorbs unrelated conversions.

---

## Construction and Mutation

| Need | Usual choice |
| --- | --- |
| Validate one or more fields during construction | `__post_init__` |
| Accept a construction input without storing it | `InitVar` |
| Validate every assignment | Named behavior method or `property.setter` |
| Update multiple fields while preserving one invariant | Named domain operation; do not expose independent arbitrary assignment |
| Prevent changes after construction | `frozen=True`, with construction checks as needed |
| Compute a derived value on access | Read-only property or method |
| Complex construction from several sources | Named factory, parser, or application service |

`__post_init__` is part of dataclass construction. It protects construction only and does not run again after direct assignment.

### Property Warnings

- Property supports value-style access, dynamic calculation, assignment control, or API compatibility; it does not inherently reduce memory.
- With dataclasses, inspect how a same-named annotated field and property interact with generated `__init__`.
- Do not hide multi-object business operations or I/O inside a setter.
- Before using `cached_property`, define what state can invalidate the value.

---

## Interface Constraints

| Need | Usual choice |
| --- | --- |
| Maintained implementations must declare a nominal relationship | `ABC` |
| Shared protected implementation or template method | `ABC` or composition |
| Third-party objects cannot change inheritance | `Protocol` |
| Static structural constraint without shared implementation | `Protocol` |
| Structural matching plus discoverable owned implementations | Explicit Protocol inheritance |
| Reliable runtime capability checks | Explicit registration, ABC, or a domain capability marker |

Do not use ABC and Protocol for the same simple contract unless nominal identity and structural compatibility are genuinely separate requirements. A Protocol should describe the minimum capability needed by its caller.

---

## Fixed Choices

| Need | Usual choice |
| --- | --- |
| A few local literal arguments | `Literal` |
| Shared choices across modules | `Enum` |
| Iteration, display labels, parsing, or member behavior | `Enum` |
| Stable string values in an external protocol | `StrEnum` or string-valued Enum, with serialization tests |
| Values supplied dynamically by deployment or a third party | String plus boundary validation, not a static Enum |

Do not create a global Enum for every pair of strings, and do not duplicate widely reused states across several Literal declarations.

For detailed Any/ABC/Protocol/Literal/Enum guidance, read [typing-interfaces.md](typing-interfaces.md). For Pydantic v2/settings or dataclass behavior, read [pydantic-v2.md](pydantic-v2.md) or [dataclass-guide.md](dataclass-guide.md).

---

## Existing-Model Migration Checklist

- Constructor inputs and coercion behavior.
- Validation exception type, location, and message dependencies.
- `repr`, equality, ordering, hashing, shallow copy, and deep copy.
- JSON, dictionary, database, and message field names and values.
- Whether defaults are shared, created per instance, or injected by validation.
- Agreement between static typing and runtime behavior.
