# Loguru Configuration Guide

## Example Application Sink

```python
from loguru import logger

handler_id = logger.add(
    "logs/app.log",
    rotation="100 MB",
    retention="14 days",
    compression="zip",
    enqueue=True,
    diagnose=False,
)
```

These values are examples, not defaults. Derive size and age from event volume, disk budget, operational retention policy, and the platform collecting logs.

---

## Exception and Context Checks

- Put `@logger.catch(reraise=True)` on a boundary only when centralized logging plus propagation is the desired behavior.
- Verify tests still receive the expected exception.
- Bind stable identifiers once instead of repeating them in every message.
- Prefer `contextualize()` for request/task-local fields in concurrent code.
- Ensure formats tolerate absent optional `extra` fields or configure defaults.

---

## Queue and Shutdown Checks

- `enqueue=True` uses a multiprocessing-safe queue and can make logging calls non-blocking; test the actual process start method and sink topology.
- Call `logger.complete()` before a child or application process exits when queued messages must be delivered.
- Await the returned object for coroutine sinks before the event loop closes.
- Do not log recursively from custom sink, rotation, retention, or compression callbacks; this can deadlock.
- Test rotation, retention, compression, multi-process writes, and graceful shutdown with a temporary directory.

Official reference:

- <https://loguru.readthedocs.io/en/stable/api/logger.html>
