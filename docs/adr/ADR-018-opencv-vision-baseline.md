# ADR-018: Native OpenCV vision baseline

Status: Accepted as benchmark baseline, 2026-10-08. Accuracy calibration still pending.

Problem: generic object and face detection must fit M1/8GB without loading multiple heavy
Python ML runtimes. Options: OpenCV DNN CPU/ONNX; ONNXRuntime; PyTorch; CoreML conversion.
Decision: start with native OpenCV DNN behind DetectorProvider and explicit unload. Use the
OpenCV Zoo YOLOX-S 2022nov and YuNet 2023mar ONNX weights, pinned to commit
47534e27c9851bb1128ccc0102f1145e27f23f98. OpenCV media is an optional package extra.

Code and weight licenses are explicitly scoped by the respective model directories:
[YOLOX](https://github.com/opencv/opencv_zoo/blob/47534e27c9851bb1128ccc0102f1145e27f23f98/models/object_detection_yolox/README.md)
Apache-2.0 and [YuNet](https://github.com/opencv/opencv_zoo/blob/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet/README.md)
MIT. Copies retained under docs/licenses. docs/models.json tracks hashes, paths, byte sizes,
revision, license provenance and replacement path. Loading rejects unknown licenses, missing
provenance, out-of-runtime paths and tampered weights. Face detection emits anonymous boxes;
it cannot create or name persistent people.

Measured on verified M1/8GB / Python 3.11.17, safe blank 640x480 inputs, 20 warm samples:
YOLOX cold 380ms, warm p50 85ms/p95 124ms; YuNet cold 11ms, p50 7.4ms/p95 7.8ms.
Process peak RSS ~347MiB includes OpenCV and sequential model loading; this is not isolated
model RAM or sustained pipeline memory. Both model references unload after measurement.
This supports initial sampled CPU inference under the provisional 500ms overlay budget,
but does not prove live phone latency, semantic accuracy or memory recovery after eviction.

Consequences: avoid PyTorch/ONNXRuntime duplication initially; add frame sampling/backpressure,
positive/negative replay data and benchmarks before marking detector tasks Done. Compare RT-DETR
or CoreML only if quality/performance measurements demonstrate need. Do not use detection or
semantic class as physical instance identity. Benchmark output: runtime/exports/vision-benchmark.json.
