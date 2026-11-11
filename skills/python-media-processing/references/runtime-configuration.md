# Media Runtime Configuration

Configure global module state in an application startup function, not at arbitrary imports. Make the function idempotent or call it exactly once before worker/process creation.

## OpenCV

```python
import cv2

cv2.setNumThreads(4)
cv2.setUseOptimized(True)
cv2.ocl.setUseOpenCL(False)
cv2.setRNGSeed(42)
```

- `setNumThreads()` affects OpenCV's following parallel regions and may interact with application/process/thread pools. Benchmark rather than matching every layer to CPU count.
- `setUseOptimized()` controls optimized dispatched code where available. Query with `useOptimized()`.
- OpenCL availability and actual use depend on the build, device, and operation. Query `cv2.ocl.haveOpenCL()` / `useOpenCL()` and benchmark correctness/performance before enabling.
- `setRNGSeed()` controls OpenCV's RNG calls; it does not seed Python, NumPy, or PyTorch.

Avoid changing these values while concurrent OpenCV work is running.

---

## Pillow

```python
from PIL import Image, ImageFile, features

webp_available = features.check("webp")
supported_features = features.get_supported()
```

- Keep `Image.MAX_IMAGE_PIXELS` protection for untrusted or user-supplied images. Setting it to `None` disables the decompression-bomb warning/error threshold and requires a documented trusted-input and resource-limit policy.
- Keep `ImageFile.LOAD_TRUNCATED_IMAGES = False` by default. Enable truncated loading only when partial recovery is an explicit product policy; verify and mark recovered output instead of silently accepting corruption.
- `Image.preinit()` loads standard plugins and is already used by Pillow internals in ordinary flows; do not call it mechanically.
- Use registration APIs only when the application owns a custom format/plugin.
- Query `features.check(...)` for optional codecs such as WebP rather than assuming the wheel/system build includes them.

---

## Decord

```python
from decord import bridge

bridge.set_bridge("torch")
# Decode work owned by the application.
bridge.reset_bridge()
```

The bridge is process-wide module state. Set it before decoding and avoid libraries changing it behind callers. Prefer an explicit conversion when shared code must support callers expecting different return types.

Decord logging APIs and accepted bridges have varied across releases. If using `decord.logging`, check the installed version and supported level constants before configuring it; do not silence errors needed by the corrupt-input policy.

---

## PyAV

```python
import av

av.logging.set_level(av.logging.ERROR)
av.logging.set_skip_repeated(True)

container = av.open(
    "rtsp://example.invalid/stream",
    options={"rtsp_transport": "tcp"},
)
```

- Prefer Python logging integration when records need normal application routing.
- Use `PYAV_LOGGING=off` only as a deployment-level choice when FFmpeg log capture must be disabled entirely.
- Container `options` are per-open settings, not module-global configuration. Validate option names against the installed FFmpeg/PyAV stack.
- `restore_default_callback()` changes the global libav logging callback; use it only when ownership and compatibility are understood.

---

## PyTorch Media

Do not add new configuration around `torchvision.set_video_backend()` or `set_image_backend()`. Torchvision video I/O and backend setters are deprecated and scheduled for removal; `set_image_backend()` no longer changes the current image-loading functions. Use TorchCodec for current PyTorch-native decoding and Torchvision for transforms/models.

Legacy `torchvision.io.read_video()` returns decoded video and audio tensors and can be convenient for already-PyTorch short-video code, but it decodes the requested interval into memory and belongs to the deprecated video-I/O path. Do not select it for long-video random sampling or new decoder architecture; use an indexed/streaming decoder appropriate to the access pattern.

If legacy code still uses these setters, treat removal as migration work and verify the installed Torchvision version. Do not suppress beta/deprecation warnings globally to preserve an obsolete path.
