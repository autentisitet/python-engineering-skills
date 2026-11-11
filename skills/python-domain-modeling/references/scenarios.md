# Python Modeling Scenarios

## API Request and Domain Value Object

An HTTP request contains `amount: "12.50"` and `currency: "cny"`. The domain requires a non-negative amount and an immutable currency.

- A Pydantic request model parses the string and reports protocol errors.
- An explicit factory converts the request into an immutable domain value object.
- Non-negative amount and immutable currency are domain invariants.
- Functions below the route do not need to depend on the HTTP request model.

---

## Dataclass Lifetime Invariant

`DateRange(start, end)` requires `start <= end` and supports shifting the entire range.

- `__post_init__` rejects an invalid initial range.
- Do not expose arbitrary independent assignment to `start` and `end`.
- Provide `shift(days)` or `replace(start=..., end=...)` so the cross-field rule is maintained in one operation.

---

## ABC and Protocol

An application owns three storage implementations and also accepts a third-party object that provides `read(key)`.

- Use ABC when owned implementations share lifecycle, protected helpers, or explicit registration.
- Let the consumer of the third-party object depend on a minimal Protocol.
- Do not copy every ABC management method into the Protocol; the callers differ.

---

## Enum and Literal

A local `render(format=...)` function accepts only `"json"` or `"text"`, and the choices are not reused elsewhere.

Use `Literal["json", "text"]`. Promote to Enum only if the choices later need shared parsing, display labels, iteration, behavior, or cross-module reuse.

---

## Reusing One Pydantic Model

A small transformation service validates input, calls pure functions, and returns the same field structure without independent domain behavior.

Reusing one Pydantic model may be appropriate. Do not duplicate objects mechanically, but confirm that future internal computation will not be constrained by external compatibility requirements.
