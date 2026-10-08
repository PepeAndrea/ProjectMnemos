# Local speech evidence — 2026-10-08

Native build recipe reproduced from the hashed official archive; tag matched the pinned commit.
Registered Tiny/Base/Silero files passed size/SHA/license gates. Native bridge matched its source
hash and all runtime dylib hashes before use. No cloud, mic, biometric enrollment or disk inference
recording occurred. Actual models processed local synthetic IT/EN voices; the English streaming
fixture produced timecoded partial/final text containing backpack and freed both model contexts.

Nine speech tests cover invalid input before loading, silence rejection, speech/pre-roll/endpoint,
max duration, split chunks, source loss/reset, anonymous speaker sessions, partial/final revision,
WER accounting and real native model unload. Latest integrated check: 67 passed, none skipped,
with MNEMOS_TEST_MODELS, MNEMOS_TEST_SPEECH and MNEMOS_TEST_POSTGRES enabled; Ruff/type checks
and all eight canonical mirror hashes verified. The legacy Starlette/httpx warning remains.

Reproduce with the speech commands in docs/runbooks/development.md. Benchmark output is
runtime/exports/speech-benchmark.json. Fixture metadata/hash is generated under datasets and
benchmark labels contain only language/stage. Warm p95 Tiny Metal ~105ms IT/~80ms EN; Silero
~0.190ms/32ms; peak process RSS ~362MiB. Error rates are 2/7 IT and 2/6 EN on only two synthetic
phrases, so these timings/positive smoke checks do not validate general acoustic accuracy.

T014/T015 remain In Progress: physical input dependency, broader VAD/WER calibration and
live-device acoustic verification are outstanding. No Epic/Milestone exit criterion is inferred
from provider tests alone. T017 voice enrollment still requires identity-authorized command flow.

Continuous capture extension: real-model paced replay through live owner-authenticated HTTP
produced first transcript ~1.754s from request (including preparation), final ~3.522s; stop
~104.1ms; audio drops 0; post-stop queue/buffer/transcript counts zero. Status responses are
no-store. Regenerable report: runtime/exports/speech-capture-http.json. Native cancellation test
observes an actual running ASR, aborts it and verifies cancellation remains sticky until unload.

Browser verification used an isolated localhost:5180 static production bundle, synthetic token
and disposable SQLite DB, with native sensor mode disabled. Observed starting -> running,
visible EN final text containing backpack with an anonymous speaker, then completed/empty
transcript at source EOF. No production token or user data entered browser automation. The
synthetic ASR spelling/error was preserved on-screen rather than silently corrected.

Startup failure is tested before any audio source opens; burst input remains <=128 queued chunks
with visible drops; stop retracts revisions and frees providers. Model preparation happens before
a shared source-clock reset, preserving paced A/V replay. T014/T015 still await native input and
representative quality calibration; no milestone is declared complete.

The isolated browser Disconnect path confirmed token input cleared, state idle, empty transcript
and protected controls disabled. Test server was stopped afterward; no test port remains needed.

Independent source-end regression: audio EOF flushes/frees speech and clears its rolling PCM
without waiting for a longer video source. The test confirms video remains running and
transcribing=false; stop then clears remaining capture state. Separate audio/video EOF flags
are included in status. This prevents unfinished speech being held behind an unrelated stream.

Latest complete suite after independent-EOF correction: 67 passed, no skips.
