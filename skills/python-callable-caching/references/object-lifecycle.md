# Python Object Lifecycle and Resource Guide

## Construction

```python
class Identifier(str):
    def __new__(cls, value: str):
        normalized = value.strip().lower()
        return super().__new__(cls, normalized)
```

Immutable built-in subclasses often need `__new__` because their value is established during creation. Ordinary mutable classes normally need only `__init__`.

Do not manually call another class's `__new__`/`__init__` as a construction workflow unless implementing a well-understood cooperative inheritance protocol.

---

## Subclass Hooks

```python
class Plugin:
    registry: dict[str, type["Plugin"]] = {}

    def __init_subclass__(cls, *, name: str | None = None, **kwargs):
        super().__init_subclass__(**kwargs)
        if name is not None:
            Plugin.registry[name] = cls
```

Use `super().__init_subclass__(**kwargs)` so multiple bases can cooperate. Registration at import time is global state: handle duplicate names, import order, tests, reloads, and plugin discovery deliberately.

---

## Deterministic Resource Protocol

```python
class Resource:
    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False
```

Return `True` only when the context manager intentionally suppresses the exception. Most resource managers return false/`None` so failures propagate after cleanup.

Use `contextlib.contextmanager` for a simple generator-shaped resource, and `ExitStack` when a dynamic number of resources must unwind in reverse order.

`__del__` is not guaranteed at interpreter exit, should not block, and cannot reliably report exceptions. `weakref.finalize` avoids some `__del__` cycle pitfalls but remains fallback cleanup rather than deterministic ownership.

Official references:

- <https://docs.python.org/3/reference/datamodel.html>
- <https://docs.python.org/3/reference/datamodel.html#with-statement-context-managers>
- <https://docs.python.org/3/library/contextlib.html>
- <https://docs.python.org/3/library/weakref.html#finalizer-objects>
