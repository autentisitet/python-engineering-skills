# Dataclass Guide

## Standard and Pydantic Dataclasses

`dataclasses.dataclass` generates methods such as `__init__`, `__repr__`, and `__eq__`; type annotations are not runtime validation. `pydantic.dataclasses.dataclass` adds Pydantic validation while retaining a dataclass interface, but mixing dataclass/Pydantic semantics can complicate serialization and ownership. Use it only for a real compatibility need.

---

## Construction and Fields

- Use `__post_init__` for construction-only validation, normalization, and derived fields. Later direct assignment does not call it.
- Use `property.setter` or named operations when every later mutation must preserve an invariant.
- Use `field(default_factory=list)`/`dict`/`set` for independent mutable defaults.
- `InitVar[T]` is an initialization-only input passed to `__post_init__` and not stored as a dataclass field.
- `ClassVar[T]` is a class variable excluded from dataclass field/init processing.
- Fields without defaults normally precede fields with defaults, including inherited-field ordering constraints.

`field()` controls `default`, `default_factory`, `init`, `repr`, `compare`, `hash`, `metadata`, and `kw_only`. Choose each from the public API rather than enabling all options.

---

## Class-Level Options

- `frozen=True` blocks generated field assignment/deletion but does not recursively freeze nested lists/dicts and is not absolute immutability.
- `slots=True` generates slots and can reduce per-instance overhead, but inheritance, weak references, pickling, dynamic attributes, and actual measurements must be checked. Use `weakref_slot=True` when appropriate rather than manually combining generated slots.
- `kw_only=True` makes generated init parameters keyword-only.
- `order=True` generates tuple-like comparisons in field definition order and requires compatible equality behavior; use `field(compare=False)` deliberately.

---

## asdict

`dataclasses.asdict()` recursively converts nested dataclasses, dicts, lists, and tuples. Other objects are copied with `copy.deepcopy()`. It follows declared dataclass fields, not arbitrary `__dict__` entries, and can be expensive or unsuitable for Pydantic/custom objects.

It returns Python objects, not guaranteed JSON. `datetime`, `Decimal`, UUID, Enum, bytes, and custom values still need an explicit JSON encoding policy. Do not expect it to invoke Pydantic's serialization logic for nested Pydantic objects.

Official reference:

- <https://docs.python.org/3/library/dataclasses.html>
