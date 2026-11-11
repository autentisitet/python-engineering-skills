# Method and Cache Selection

| Need | Usual choice |
| --- | --- |
| Depends on instance state | Instance method |
| Polymorphic alternative constructor | classmethod |
| Stateless helper that belongs to a class concept | staticmethod, after considering a module function |
| Low-cost derived value without visible side effects | Read-only property |
| Preserve a local invariant on each assignment | `property.setter` or a clearer named operation |
| Compute once for an effectively stable instance | cached_property |
| Pure function with bounded argument space | cache |
| Capacity-limited recent-value cache | lru_cache |
| External or time-sensitive result | Explicit cache object with TTL/versioning, or no cache |

Cached functions should be close to pure: equal cache keys should produce equivalent results, required side effects must not be skipped, and validity must not depend on untracked changing state.

## Review Questions

- Does a classmethod actually use `cls` and preserve subclass behavior?
- Is a staticmethod related to the class, or clearer as a module function?
- Does a property hide I/O, lock waiting, expensive recomputation, or significant failures?
- Can state used by a cached_property change, and how is the cached attribute removed?
- Does an lru_cache key containing `self` retain instances too long?
- Are exceptions cached, or will the same failure execute repeatedly?
- Does cache state leak across tests, requests, tenants, or configuration versions?
- Can `del instance.cached_attribute` safely invalidate a `cached_property`, and who owns that action?
- Does the instance have a writable `__dict__`, or do slots/metaclass/proxy constraints make `cached_property` invalid?
- Is an unbounded `cache`/`lru_cache(maxsize=None)` argument space actually bounded by the application?

`cached_property` computes on first missing attribute access and then writes the value into the instance dictionary. Normal attribute writes can override it. It may interfere with key-sharing dictionaries and increase instance memory. Python 3.12+ no longer includes the earlier undocumented per-property lock, so concurrent first reads can compute more than once.

`lru_cache` and `cache` retain arguments and return values until eviction/clear. For methods, the key includes `self`, which can retain instances. The wrappers are coherent across threads, but simultaneous misses may execute the underlying callable more than once.

Official reference:

- <https://docs.python.org/3/library/functools.html>
