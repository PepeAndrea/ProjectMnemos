# Source failure and recovery verification

2026-10-09: 140 tests passed/no skips with model/speech/PostgreSQL opt-ins; lint/format,
mypy (60 sources), eight mirror hashes and replay pass. Web build passes (36 modules,
JS 266.03KB / gzip 80.75KB). T007/T013 stay In Progress.

tests/test_source_failures.py checks camera constructor/configuration/read/format failures,
camera/file distinctions, empty versus normal EOF, nonfinite FPS fallback, microphone opening/
context-entry/read failure, source cleanup, first-cause preservation, live-worker status,
release failure, and a read error arriving during deliberate Stop. Secret fixture exception
text does not appear in public state. Existing native consent guards remain covered.

```sh
runtime/core-venv/bin/python -m mnemos.source_failure_verify
```

Real isolated Uvicorn/HTTP with temporary SQLite/runtime root: unauthenticated status denies;
simulated camera opening fails while its cleanup worker is held; second start returns 409
without creating another source. Releasing the gate yields terminal worker state and preserves
the first error. Explicit new start creates a distinct session with generated JPEG preview;
Stop clears media/worker state. Server, temporary DB/root and socket cleaned at exit.
Reports: runtime/exports/source-failure-http.json and source-failure-benchmark.json.
Latest cleanup after gate release 92.64ms; 50 warm simulated faults p95 110.28ms.

Isolated browser 5186: observed failed state with Stop enabled/new starts disabled while a
worker was live. After cleanup, the restart control enabled. A new explicit replay produced
preview and removed the previous error. Stop removed feed/forms; Disconnect cleared token and
state. Screenshots: source-failure-dashboard.jpg and source-recovery-dashboard.jpg under
runtime/exports. No native mode or real media used. Synthetic fixture DB/source retained under
runtime/tmp/ui-source-failure-test*. Server cleanup is performed after verification.

Real camera/root-cause verification is pending: an earlier production attempt had camera and
microphone selected but no video frame, with generic source/normalization failure. Do not infer
missing OS permissions or claim hardware recovery from these simulations. AVFoundation is
present in the installed OpenCV build; that alone does not establish device access.

ADR-033 adds a bounded five-index native camera probe after explicit consent. A candidate must
open and return its first frame; failed handles are released before trying the next index.
`tests/test_media.py` simulates an unavailable first index and an opened-but-frame-less first
index, verifies selection of the next usable camera and cleanup, and checks sanitized failure
when every candidate fails. Real webcam/Continuity Camera behavior remains to be verified on the
Mac; synthetic tests do not close T007.

Manual camera selection (ADR-033): dashboard offers Automatic or indices 0–4, disables the selector
without camera consent, and sends the chosen index only for native camera capture. Backend rejects
out-of-range indices and any index on non-native/audio-only requests. `test_build_capture_uses_explicit_camera_index_without_opening_device` verifies routing without
accessing hardware. Production web build: 37 modules, JS 269.27KB (gzip 81.57KB). Core restarted;
`/health` returned 200 and authenticated out-of-range camera index returned 422. Native webcam
preview and physical camera naming remain unverified.
