---
name: python-media-processing
description: Configures OpenCV/Pillow/Decord/PyAV runtime behavior and chooses decoding libraries, video sampling, timestamps, codecs, and RGB/HSV/Lab/YUV/YCrCb representations. Use when those media-pipeline decisions are substantive. Never activate for torchvision or generic tensor/image augmentations after decoding, chart styling, or incidental media-library mentions.
metadata:
  short-description: Configure media libraries, sampling, and color spaces
---

# Python Media Processing

## Activation

- **Keyword trigger:** the task substantively involves `cv2`, OpenCV, Pillow/PIL, Decord, PyAV, TorchCodec, media runtime configuration, frame sampling, cameras, codecs, timestamps, or RGB/HSV/Lab/YUV/YCrCb selection.
- **Intent trigger:** the user asks which media library, module-level setting, sampling strategy, representation, or color space should own a Python image/video operation.
- **Disclosure:** once when starting applicable work, briefly state: `Using $python-media-processing because this task involves media-library configuration or selection.`
- **Exit:** stop applying this skill when runtime configuration, library responsibility, sampling, and color representation are settled.
- **Do not trigger:** a media-library name in documentation, dependencies, or unrelated logs is insufficient. Generic augmentations or transforms applied to tensors/images that are already decoded are outside this skill unless decoding, media representation, color conversion, or media runtime configuration is also changing.

---

## Separate Environment From Module Configuration

Most settings in this skill are process-wide **module APIs**, not environment variables. Configure them once in an application-owned startup function, before workers or media objects are created. Do not mutate them in reusable library imports.

Review only settings that change real behavior:

- OpenCV `cv2.setNumThreads()`, `setUseOptimized()`, OpenCL use, and `setRNGSeed()`;
- Pillow `MAX_IMAGE_PIXELS`, `LOAD_TRUNCATED_IMAGES`, and plugin/feature availability;
- Decord `bridge.set_bridge()` / `reset_bridge()` and decoder log level; and
- PyAV logging plus per-container `av.open(..., options=...)` settings.

Read [references/runtime-configuration.md](references/runtime-configuration.md) before changing global state. Record the effective setting when reproducibility or performance depends on it.

---

## Assign Each Library a Clear Responsibility

- **Pillow:** common image read/write, resizing, crop/rotate/geometry, saving, and text/watermark composition. Use it for Chinese text only with an explicit font file; OpenCV's built-in Hershey text renderer is not a general Unicode/CJK renderer.
- **OpenCV:** cameras, real-time capture, traditional CV algorithms, NumPy-oriented processing, and explicit color conversion. Handle capture latency, failed reads, and `release()`.
- **Decord:** fast indexed/batched video frame sampling for training or offline analysis. It is not the first choice for a live camera.
- **PyAV:** stream/container control, packet/frame/time-base semantics, multi-stream synchronization, remuxing, codec/format selection, and precise timestamps.
- **TorchCodec:** current PyTorch-native decoding when decoded media should enter a tensor pipeline directly. Keep Torchvision for transforms/models; do not design new code around deprecated Torchvision video I/O or backend setters.

Read [references/library-selection.md](references/library-selection.md) for boundaries and verification.

---

## Choose the Sampling Strategy From the Task

State whether sampling is based on frame indices, timestamps, decoded content, or keyframe metadata. Select deliberately:

- uniform sampling for broad whole-video coverage;
- segment-random sampling for training diversity across the full duration;
- fixed-FPS sampling for time-normalized analysis and cross-video comparison;
- random contiguous clips for motion/temporal models;
- center-dense sampling when the middle is known to contain the target event;
- sliding-window multi-clip sampling for long-event coverage and inference aggregation;
- keyframe sampling for coarse navigation or compressed-domain workflows, not unbiased visual coverage;
- motion/frame-difference sampling for change-focused workloads;
- redundant candidate sampling plus quality filtering when blur, corruption, blank frames, or occlusion are common; and
- multi-scale temporal sampling when events occur at several durations.

For variable-frame-rate media, use timestamps rather than assuming frame index / nominal FPS is exact. Validate seek accuracy, duplicate frames, corrupt input, and memory use.

---

## Select the Color Space by the Algorithm

- **RGB:** display, Pillow, most pretrained neural-network inputs, and general color representation. Convert OpenCV BGR explicitly.
- **HSV:** hue-oriented thresholds and color segmentation when illumination changes are moderate; handle hue wrap-around and low-saturation instability.
- **Lab:** perceptual color distances, color correction, and separating lightness from chroma; verify conversion ranges and dtype conventions.
- **YUV/YCrCb:** luminance/chroma separation, skin/color heuristics, compression/video-oriented processing, and some illumination-robust operations. Confirm the exact matrix, range, and channel ordering used by the library/format.

Do not convert merely because an algorithm example used a color space. State channel order, dtype, numeric range, and layout at every library boundary.

---

## Required Output

Report only relevant decisions: application-owned runtime configuration, library responsibility, input/output representation, sampling basis and strategy, selected color space and conversion contract, timestamp semantics, corrupt-input policy, cleanup ownership, and target-platform feature checks.
