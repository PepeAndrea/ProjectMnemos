# Foundation evidence — 2026-10-08

Hardware verified: Apple M1 / 8GB (8589934592 bytes), macOS 26.6.2 arm64.
Official runtime: CPython 3.11.17, exact Python packages/hashes in uv.lock.

Verified with scripts/check: Ruff check + format, strict mypy and 54 passing tests with all model/PostgreSQL opt-ins enabled and no skipped tests.
The PostgreSQL test passed against
the real local pg17/pgvector service, on both bootstrap Python and official Python 3.11.
Migration 0001_registry applied and vector distance SQL executed successfully. Container healthy.
Tests cover schema round trips, unknown person rejection, biometric reference consent,
non-finite scores, timecodes, partial audio boundary, auth missing/invalid, manual registry
create/update/restart, duplicate/not-found failures, bounded queues/buffers, path/symlink
escapes, model risk spoofing, third-party command rejection, compound/time reminders, three-way
Drive sync conflict handling, fixture mismatch, media source shared clock and resource cleanup.

Generated safe replay: 4 PPM frames, 4-second 16kHz PCM tone, 4 expected lifecycle events.
OpenCV replay decoded 4 generated MJPEG frames and WAV source emitted 200 aligned chunks.
Neither camera nor microphone was activated. No real person, recording or cloud inference.

Resource benchmark: 20,000 iterations in ~0.048s, buffer 1,048,320 bytes <=1,048,576 budget,
queue bounded to 4 with 19,996 stale-item drops. p95 append ~0.00067ms, queue put ~0.00062ms.
These are synthetic infrastructure timings; no ML accuracy, phone latency or throughput claim.
Rerun `python -m mnemos.benchmark` on the official profile; output runtime/exports.

Five Drive files freshly read via connected personal Drive account; local hashes verified and
remote modified timestamps recorded in manifest. Canonical CSV plan is unchanged; local Done
ledger marks T001–T006, T046, T088, T089 and T093 with objective evidence. T017,
live acquisition/perception and Drive write sync remain In Progress. No milestone is declared complete.

Known check warning: installed Starlette recommends httpx2 for future TestClient compatibility;
current httpx-backed contract tests pass. This is not a failing test or production dependency.

Actual perception replay passed: public-domain NASA/scikit-image positive photograph followed
by blank negatives; YOLOX person and YuNet anonymous face detection, session tracking lifecycle
enter/update/exit/enter, face counts [1,1,0,1], and 200 shared-clock audio chunks. Fixture/source
checksum in runtime/datasets/public; no face enrollment or biometric recognition. This is a
small regression fixture and cannot calibrate accuracy on general scenes.

Frontend: pnpm frozen install + TypeScript/Vite production build passed. Manual browser review
confirmed rendered dashboard, rejected invalid token with visible error, and Disconnect cleared
input and private catalog state. Backend REST CRUD verified by contract tests; browser did not
create real user data. Generated web build and Vite cache are under runtime.

Continuous capture verification: actual owner-authenticated loopback HTTP start/status/JPEG/stop
passed with installed YOLOX/YuNet and the public replay. Preview 31,608 bytes; inference ~231ms;
stop ~85ms; queue and both buffer byte counts zero after stop. Report regenerable at
runtime/exports/capture-http-verification.json. No physical camera/microphone or cloud call.
Native Docs/Sheets transport is implemented and simulated-response tested, including failed
readback and local rollback. All eight mirror hashes verify. Live OAuth/publishing is unverified.
Latest full check: 54 tests passed, none skipped (model and real PostgreSQL opt-ins enabled).

T046 temporal reminder acceptance passed with transaction rollback/restart/authorization tests,
isolated PostgreSQL concurrency, live loopback HTTP and documented synthetic benchmark.
See temporal-reminders.md. The local evidence ledger now contains ten Done tasks.

Idle-media retention regression fixed: independent expiration checks run every 100ms while
capture is active, including audio-only sessions; byte budgets also include a 20,000-chunk ceiling
to bound Python object overhead. Empty packets are not retained. Idle expiry/tiny-packet tests
pass. Updated 20,000-iteration resource benchmark: ~0.051s, buffer p95 ~0.00071ms, queue
p95 ~0.00063ms, payload bytes 1,048,320 within 1MiB budget. Latest full suite: 54 passed, no skips.
Fresh browser review confirms disconnected dashboard, disabled protected controls, separate
unchecked sensor consents and the temporal-reminder form. Live notification semantics were
verified through authenticated HTTP; no production token was entered into browser automation.

Speech provider extension verified: 62 integrated tests passed with all real-model/DB/speech
opt-ins enabled, no skips. See speech.md and ADR-021 for native build/model provenance, actual
partial/final replay, latency/WER comparison and remaining integration/calibration work.

Continuous speech now verified through core capture + live HTTP + isolated production-bundle
browser. Latest integrated suite: 67 passed, no skips, with all real model/speech/PostgreSQL opt-ins.
See speech.md for timing, privacy, cancellation and remaining physical/calibration boundaries.

Governed manual non-person registry mutations now pass policy + atomic audit and reject
consent/reference spoofing. Latest full suite: 73 passed, no skips. See registry.md / ADR-022.

Governed non-person delete and dashboard rename/confirmation gating verified; latest suite:
76 passed, no skips. Synthetic benchmark covers 300 atomic mutation/audit pairs. See registry.md.

Reviewed final-ASR catalog proposals and their authorization/TTL/stop boundaries verified.
Latest suite: 92 passed, no skips. Real Whisper → HTTP → PostgreSQL plus isolated dashboard
review passed; physical/person enrollment still pending. See voice-enrollment.md / ADR-023.
