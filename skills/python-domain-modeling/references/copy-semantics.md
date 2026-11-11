# Python Model Copy Semantics

## Behavior Table

| Operation | Outer object | Nested mutable objects | Internal repeated references |
| --- | --- | --- | --- |
| Assignment | Shared | Shared | Unchanged |
| `copy.copy()` | Usually new | Shared | Still refer to original children |
| `copy.deepcopy()` | Usually new | Recursively copied when supported | Preserved within the copied graph through memoization |
| pickle dump/load | Reconstructed according to pickle protocol and type hooks | Usually reconstructed for serialized state | Pickle memo can preserve aliases/cycles |

These are semantic defaults, not promises that every object is new. Deep-copy memoization also prevents infinite recursion for cyclic graphs. Check type-specific hooks.

---

## Example

```python
import copy

shared = []
original = {"left": shared, "right": shared}

shallow = copy.copy(original)
deep = copy.deepcopy(original)

assert shallow is not original
assert shallow["left"] is shared

assert deep is not original
assert deep["left"] is not shared
assert deep["left"] is deep["right"]
```

The deep copy creates one copied child and preserves the original graph's internal alias relationship.

---

## Custom Types

- Implement `__copy__()` for explicit shallow semantics.
- Implement `__deepcopy__(memo)` when some fields must be copied, shared, reset, or reconstructed.
- Insert the new object into `memo` before recursively copying cyclic children.
- Prefer named clone/factory methods when the operation has domain semantics different from generic copying.
- Test identity (`is`) and mutation propagation, not only equality.

Official references:

- <https://docs.python.org/3/library/copy.html>
- <https://docs.python.org/3/library/pickle.html>
