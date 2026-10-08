# ADR-019 — Continuous local capture and native Drive synchronization

Status: Accepted for reversible implementation, 2026-10-08.

Two integration boundaries require explicit failure and privacy behavior. Native sources can
block reads, and the canonical operational plan is a Google Sheet rather than a Google Doc.

Capture uses source threads, a two-frame latest-wins queue and a single sampled local inference
worker. Video buffer is JPEG sampled at 1 FPS/320 pixels (64MiB max); PCM is bounded to 16MiB;
both also expire within 300 seconds. No raw media is written. Each sensor needs independent
strict boolean consent, owner authorization and sensor_start PolicyEngine approval. Stop clears
media immediately and waits up to five seconds; an unresponsive worker leaves a visible failure
and blocks a new session. Disconnect waits for confirmed stop. Normal EOF and inference/source
failure clear buffers and evict models. No OS permission was granted during implementation.

Actual loopback replay with local YOLOX/YuNet produced a 31,608-byte preview, first inference
~231ms and stop ~85ms on M1/8GB. This short regression fixture validates plumbing, not sustained
camera throughput or general accuracy. Queue overflow, missing media dependency, source failure,
stop, authentication and independent consent are tested.

Drive sync derives normalized plan CSVs with independent baseline hashes and local rollback.
Live native Docs transport uses guarded paragraph replacements; Sheets uses narrow RAW patches.
Post-write readback gates baseline advancement. General implementation authorization does not
include canonical publishing. Fake transport/API tests verify conflicts and readback; actual
OAuth/write roundtrip remains pending. Sheets cannot provide a revision-conditional write, so
an authorized operator must pause collaborative edits. No extra dependency or service is needed.

Retention correction: age eviction cannot depend only on append. Independent 100ms checks expire
idle media, and a 20,000-chunk cap bounds small-packet object overhead. Synthetic benchmark
remains ~0.051s/20k iterations; idle-expiry and pathological tiny-packet regressions pass.
