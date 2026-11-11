---
name: python-callable-caching
description: Chooses Python callable ownership, including lambda versus named function and method versus module placement, plus properties, closures, cache lifetimes, construction/subclass hooks, and deterministic cleanup. Use when those design decisions affect reuse, binding, tracebacks, state, or lifetime. Do not use for ordinary calls to partial or other higher-order helpers, browser/distributed/external caches, dependency maintenance, or isolated syntax.
metadata:
  short-description: Choose Python methods and caches with explicit lifetime and invalidation
---

# Python Callable and Caching Design

## Activation

- **Keyword trigger:** the task substantively involves choosing lambda versus a named function, method versus module placement, closure, `property`, `classmethod`, `staticmethod`, caches, `__new__`, `__init_subclass__`, `__del__`, context managers, or resource ownership.
- **Intent trigger:** the user asks to review callable placement, binding, reuse/traceback tradeoffs, class construction, subclass registration, properties, caches, or deterministic cleanup.
- **Disclosure:** once when starting applicable work, briefly state: `Using $python-callable-caching because this task involves ...`.
- **Exit:** stop applying this skill when the task no longer concerns method binding, descriptors, or caching.
- **Do not trigger:** merely calling `functools.partial`, `map`, `filter`, or another existing callable helper is insufficient when callable ownership, binding, state, reuse, tracebacks, caching, and lifetime are not being designed.

---

## Decide Callable Ownership

- Use an instance method when behavior depends on instance state or polymorphism.
- Use `classmethod` for an alternative constructor or operation that intentionally depends on the concrete subclass through `cls`.
- Use `staticmethod` when logic belongs conceptually to the class namespace but depends on neither instance nor class state. Prefer a module-level function when there is no class-level concept.
- Use property when access is value-like, predictable, and low in side effects. Expensive work, I/O, or important failure behavior usually belongs in an explicit method.
- Use a lambda only for a short expression whose meaning remains obvious at the call site. Use a named function when behavior needs a docstring, annotations, tests, reuse, multiple statements, or useful tracebacks.
- Use a closure when captured lexical state is the intended API and its lifetime/mutability are clear. Prefer an object when state needs several operations, introspection, explicit mutation, serialization, or lifecycle management.

Read [references/callable-guide.md](references/callable-guide.md) for binding, property, lambda, and closure decisions. Read [references/cache-guide.md](references/cache-guide.md) for cache selection. Read [references/object-lifecycle.md](references/object-lifecycle.md) when allocation, subclass hooks, finalizers, or context managers matter.

---

## Preserve Property and Descriptor Semantics

- Property supports computed values, assignment control, or API compatibility; it does not reduce memory by itself or make complex construction logic simpler merely by moving it out of `__init__`.
- A setter must preserve lifetime invariants. Use a named operation when mutation spans several objects, performs I/O, or represents a visible business action.
- `property.getter`, `.setter`, and `.deleter` create descriptor variants for attribute access. Do not add setters/deleters unless public assignment/deletion is genuinely part of the API.
- `cached_property` normally stores its result in the instance namespace after first access. Later state changes do not invalidate it automatically.
- Before using `cached_property`, confirm compatibility with writable `__dict__`, slots, custom attribute storage, mutability, key-sharing dictionary memory, and object lifetime.

---

## Design Function Caches Explicitly

- Use `cache` for pure functions whose argument space is naturally bounded and whose results remain valid. Otherwise its unbounded growth can become a memory leak.
- Size `lru_cache(maxsize=...)` according to the working set and object lifetime rather than using the default `maxsize=128` mechanically. `maxsize=None` is unbounded and is equivalent in purpose to `cache` with a thinner wrapper.
- Cache keys follow argument hashing and equality. Including mutable concepts, `self`, or large objects may retain them longer than expected.
- Thread-safe cache bookkeeping does not guarantee that the underlying function executes only once for simultaneous misses. Design single-flight behavior separately when required.
- Do not cache time-, environment-, file-, database-, or network-derived results without TTL, versioning, explicit clearing, or another invalidation rule.
- Inspect with `cache_info()` and clear with `cache_clear()` for diagnostics/tests; do not make business behavior depend on hit counts.

---

## Test and Observe

- Test hits, misses, eviction, and invalidation, not only returned values.
- Expose cache information only for diagnostics; business logic should not depend on hit counts.
- Clear process-wide caches between tests to avoid order dependence.
- Before replacing an implementation, check whether caching affects object identity, repeated exceptions, memory retention, or a caller-visible performance contract.

---

## Own Resources Deterministically

- Use `__new__` only for creation/allocation behavior that `__init__` cannot express, especially immutable subclasses or controlled construction.
- Use `__init_subclass__` for lightweight cooperative subclass validation/registration; call `super()` and handle import-order/global-registry risks.
- Do not rely on `__del__` for files, sockets, locks, transactions, or other correctness-critical cleanup. Prefer context managers and idempotent `close()`/`aclose()`.
- Use `ExitStack`/`AsyncExitStack` for a dynamic resource set. Treat finalizers only as noncritical fallback cleanup.

---

## Required Output

Report only the items relevant to the requested change; do not impose a full review on a small task.

State whether the callable belongs to an instance, class, or module; whether property access is genuinely value-like; cache key, size, and lifetime; invalidation and clearing; concurrent-miss behavior; and correctness/memory verification.
