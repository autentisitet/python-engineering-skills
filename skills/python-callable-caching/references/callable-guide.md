# Callable and Descriptor Guide

## Binding Table

| Definition | Automatically receives | Typical use |
| --- | --- | --- |
| `def method(self, ...)` | Current instance | Read or modify instance state; polymorphic behavior |
| `@classmethod def method(cls, ...)` | Current class | Alternative constructors; subclass-aware class behavior |
| `@staticmethod def method(...)` | Nothing | Class-related helper independent of instance/class state |
| `@property def name(self)` | Current instance | Value-like computed/access-controlled attribute |

A classmethod may be accessed through the class or an instance, but its first argument remains the class (`type(instance)` or a subclass), never `self`. A staticmethod may also be accessed through either, but no instance/class argument is injected.

Prefer a module function over staticmethod when the helper has no meaningful class concept. Prefer classmethod when `cls(...)` must preserve subclass construction.

---

## Property Semantics

Use a property for cheap, predictable, value-like access or compatibility with an attribute API. A computed property such as `area` avoids storing a redundant derived field, but property itself does not shrink `width`/`height` or replace `__dict__`; use `slots` only after measuring its actual memory tradeoff.

Use `__post_init__`, an explicit factory, or straightforward constructor validation for construction-only logic. Use a property setter only when later public assignment must validate every change. Do not hide I/O, long computation, locking, or business commands behind attribute syntax.

`property.getter`, `.setter`, and `.deleter` return new property objects; conventional decorator assignment keeps the same attribute name.

---

## Lambda and Closures

Good lambda uses are short local expressions such as a sorting key:

```python
records.sort(key=lambda item: item.created_at)
```

Avoid assigning complex lambdas to names; a `def` provides a name, annotations, documentation, clearer tracebacks, and statements.

A closure can create a configured callable:

```python
def make_validator(limit: int):
    def validate(value: int) -> bool:
        return value <= limit
    return validate
```

Captured objects remain alive as long as the closure. Use `nonlocal` only for intentional mutable closure state. Prefer a callable object/dataclass when state ownership, reset, introspection, several methods, or serialization matter.

Official references:

- <https://docs.python.org/3/howto/descriptor.html>
- <https://docs.python.org/3/reference/expressions.html#lambda>
- <https://docs.python.org/3/reference/executionmodel.html#resolution-of-names>
