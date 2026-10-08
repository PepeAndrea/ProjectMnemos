# Face quality and synthetic positive replay

2026-10-08: full suite 127 passed/no skips; lint/format, mypy (59 sources), eight mirror hashes
and replay pass. Web build passes. T018/T012 remain In Progress.

tests/test_face_quality.py verifies generated sharp/blurred patterns, tilt/asymmetry, eye-order
invariance, missing/degenerate/out-of-crop/nonfinite geometry, relative coordinates, provider
schema, raw-point public redaction and failure/track-loss cleanup. The real YuNet opted-in test
uses one hash-pinned fictional AI portrait, no real subject.

```sh
runtime/core-venv/bin/python -m mnemos.face_quality_benchmark
runtime/core-venv/bin/python -m mnemos.face_quality_replay
runtime/core-venv/bin/python -m mnemos.face_reference_http_verify
```

Reports under runtime/exports: face-quality-benchmark.json (six generated cases, 50 repeats),
face-quality-replay.json (ten repeats of one AI image), face-reference-http.json.
Actual YuNet finds one face/five points; crop stores derived uncalibrated geometry only.
Observed detector max/p95 of ten repeats ~104ms, crop+quality+encode ~10.3ms. HTTP/PostgreSQL
checks geometry in authorized listing, no raw points in capture state, independent view deletion,
consent revocation and cleanup. Latest save 60.74ms, cleanup 954.90ms.

Thresholds are provisional (ADR-031). This does not prove real-scene detection accuracy, view
diversity, 3D pose, recognition or representative quality. Isolated browser 5185 passed actual YuNet continuous capture over the AI image, explicit reference save, uncalibrated geometry text (3 degrees), preview after Stop, persistence across server restart and image/token/person clearing on Disconnect. Screenshot runtime/exports/face-quality-dashboard.jpg. Server stopped normally; native modes disabled throughout. Synthetic fixture DB/media/key remain isolated under runtime/tmp/ui-face-quality-test*.
