---
name: python-loguru-logging
description: Configures and reviews Loguru exception capture, bound context, file sinks, rotation, retention, compression, queued logging, and shutdown completion. Use when project failure and deployment requirements justify those features. Do not use for standard-library logging, observability vendors, or incidental logger calls.
metadata:
  short-description: Configure Loguru exceptions, context, sinks, and shutdown
---

# Python Loguru Logging

## Activation

- **Keyword trigger:** the task substantively involves Loguru, `logger.catch`, `logger.bind`, `logger.contextualize`, `logger.add`, `rotation`, `retention`, `compression`, `enqueue`, or `logger.complete`.
- **Intent trigger:** the user asks to improve Loguru exception boundaries, structured context, file lifecycle, multiprocessing delivery, or shutdown behavior.
- **Disclosure:** once when starting applicable work, briefly state: `Using $python-loguru-logging because this task involves Loguru configuration.`
- **Exit:** stop applying this skill after exception, context, sink ownership, and shutdown decisions are complete.
- **Do not trigger:** a generic logging request using the standard library or a logger name appearing only in unrelated code is insufficient.

---

## Review Exception Boundaries

- Consider `@logger.catch` at process, worker, command, callback, or task boundaries where one place should log an otherwise uncaught exception.
- Do not decorate every custom function. Broad catch/log layers can duplicate traces, obscure ownership, or suppress errors.
- Check `reraise`: the default can prevent propagation. Use `reraise=True` when callers, supervisors, tests, or retry logic must still observe failure.
- Prefer ordinary `try`/`except` when recovery, translation, cleanup, or different handling by exception type is required.
- In production, review `diagnose=False` where exception diagnostics could expose local values or secrets.

---

## Bind Stable Context

- Use `logger.bind(...)` for stable context attached to a component or operation, such as job, tenant, request, or object identity.
- Use `logger.contextualize(...)` for scoped context that should follow the current thread or async task.
- Include bound fields in sink formats or serialized records; binding unused fields adds complexity without improving logs.
- Do not bind secrets, tokens, full payloads, or unbounded high-cardinality objects.

---

## Configure File Lifecycle Deliberately

For file sinks, decide from deployment requirements whether to use:

- `rotation="... MB"` for a size limit or another supported time/size policy;
- `retention="... days"` to remove old matching files;
- `compression="zip"` to archive rotated/closed files; and
- `enqueue=True` for non-blocking calls and a multiprocessing-safe queue when concurrency requires it.

The option is spelled `retention`. Do not add rotation, retention, compression, or queuing mechanically: container stdout collection, external log rotation, disk limits, multi-process topology, and shutdown ownership may call for a different design. Avoid configuring the same file sink independently in multiple spawned processes.

Read [references/loguru-guide.md](references/loguru-guide.md) for shutdown and verification details.

---

## Complete and Shut Down

- Call `logger.complete()` when the application owns handlers with `enqueue=True` and must flush queued messages before process exit, especially around multiprocessing boundaries.
- For coroutine sinks, `await logger.complete()` before the owning event loop closes.
- Keep handler IDs when explicit removal and lifecycle management are required.
- Treat logging failure policy separately from application exception policy; sink `catch` and `logger.catch` solve different problems.

---

## Required Output

State the exception boundary and propagation behavior, bound/contextual fields, sink ownership, rotation/retention/compression rationale, queue and multiprocessing behavior, sensitive-data controls, and shutdown/`complete()` path.
