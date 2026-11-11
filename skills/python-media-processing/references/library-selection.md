# Image and Video Library Selection

| Need | Evaluate first | Main risks |
| --- | --- | --- |
| Image read/write, resize, geometry, saving, Unicode text | Pillow | Mode, EXIF orientation, decompression limits, explicit font files |
| Cameras, real-time capture, traditional CV, NumPy arrays | OpenCV | BGR/RGB, latency, failed reads, release, build features |
| Fast indexed/batched offline frame sampling | Decord | Wheels/builds, bridge global state, seek accuracy, corrupt input |
| Streams, remuxing, codecs, time bases, exact timestamps | PyAV | Packet/frame semantics, per-container options, cleanup |
| Current PyTorch-native image/video/audio decoding | TorchCodec | PyTorch/FFmpeg compatibility, format and device support |
| Tensor transforms, datasets, and models | Torchvision | Video I/O is deprecated; do not make it the long-term decoder |

Pillow can render Chinese watermarks when supplied with a font containing the glyphs. OpenCV's built-in `putText()` uses limited Hershey fonts; alternatives include Pillow composition or OpenCV's optional FreeType module when the build provides it.

---

## Sampling Verification

Test representative constant- and variable-frame-rate files, short and long GOPs, corrupt/truncated inputs, and the target duration/resolution. Verify:

- returned frame count and ordering;
- frame-index versus timestamp semantics;
- seek accuracy and duplicate/missing samples;
- batch memory and tensor/array layout;
- deterministic behavior under a controlled RNG; and
- whether the chosen strategy matches training or product semantics.

Do not infer that keyframes are the most visually informative frames. They are codec random-access points. Do not declare a decoder fastest from one file/hardware measurement.

---

## Representation Contract

At every boundary state:

- RGB/BGR/HSV/Lab/YUV/YCrCb and any exact variant;
- HWC/CHW/THWC/TCHW layout;
- integer/float dtype and numeric range;
- CPU/GPU ownership and copy behavior; and
- frame timestamp/time-base meaning.

Official/current references:

- <https://docs.opencv.org/4.x/>
- <https://pillow.readthedocs.io/en/stable/>
- <https://github.com/dmlc/decord>
- <https://pyav.org/docs/stable/>
- <https://docs.pytorch.org/torchcodec/stable/>
- <https://docs.pytorch.org/vision/stable/io.html>
