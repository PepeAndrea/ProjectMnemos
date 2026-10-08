# Face reference verification — partial T018

Full regression: 122 tests passed, no skips; lint/format, mypy (56 sources), all eight mirror hashes and contract replay pass. Migration version/table verified in PostgreSQL as 0005_face_references/face_references.

2026-10-08: consent-bound image storage/API implemented; dashboard built and isolated browser flow verified. No real subject or native sensor used. Generated pixels and fake face boxes test
orchestration, not detection, identity or biometric quality. T018 remains In Progress.

`tests/test_face_references.py` checks face-versus-voice scope, explicit confirmation/current
name, consent/reference expiry, encrypted permissions, separate keys/tables, stale/partial/small/
overlapping crops, stop behavior, audit rollback, missing-key refusal and filesystem retry.
PostgreSQL concurrent acquisition/revocation verifies lock ordering and immediate access denial.

Reproduce full checks:

```sh
MNEMOS_TEST_MODELS=1 MNEMOS_TEST_SPEECH=1 \
MNEMOS_TEST_POSTGRES=postgresql+psycopg://mnemos:mnemos@127.0.0.1:5432/mnemos scripts/check
runtime/core-venv/bin/python -m mnemos.face_reference_http_verify
runtime/core-venv/bin/python -m mnemos.face_reference_benchmark
```

The HTTP verifier uses real Uvicorn/PostgreSQL in an isolated schema/private temporary root.
Two distinct views persist after Stop, tracks remain anonymous, deleting one view preserves
the other, consent revocation denies both immediately and the worker deletes encrypted files.
Schema, files, private key and server are cleaned afterward. Results:
runtime/exports/face-reference-http.json (save 68.46ms, cleanup 865.02ms).

50 synthetic SQLite samples: p95 crop/store/read/retire 0.35/3.55/1.85/3.19ms, recorded in
runtime/exports/face-reference-benchmark.json. These are storage costs, not recognition metrics.
Isolated loopback 5184 browser verification passed: explicit selection/unchecked confirmation, save, quality warnings, preview after Stop, persistence after reload/reconnect and token/person/blob clearing on Disconnect. Screenshot: runtime/exports/face-reference-dashboard.jpg. Only generated pixels and synthetic metadata; no native permissions or real participant. Test server stopped normally; synthetic SQLite/media/key fixtures remain isolated under runtime/tmp/ui-face-reference-test*.
