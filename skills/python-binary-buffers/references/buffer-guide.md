# Binary Buffer Selection

| Need | Usual choice |
| --- | --- |
| Immutable complete message | bytes |
| Incremental assembly or in-place edits | bytearray |
| View part of a buffer without copying | memoryview |
| Fixed-field binary structure | struct |
| Integer field encoding | `int.to_bytes` / `int.from_bytes` |
| Text field inside a protocol | Explicit charset and error policy with encode/decode |
| Large-file hashing or forwarding | Fixed-size chunked reads |
