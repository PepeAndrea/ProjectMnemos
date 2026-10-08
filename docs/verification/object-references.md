# Explicit object crop persistence — 2026-10-08

110 tests pass with installed local models/speech and real PostgreSQL opt-in, no skips;
Ruff/format/strict mypy, eight source mirror hashes and replay pass. Additive migration
0004_object_references applied to local PostgreSQL. No production image/key was acquired.

Tests/test_references.py verifies generated synthetic BGR frames → explicitly bound crop →
encrypted contained file → linked Entity.reference_ids + audit → authenticated audited read
→ strong-confirmed logical revocation → physical cleanup. Actual PostgreSQL roundtrip uses
isolated test_references_* schema dropped at exit. API uses TestClient, not a live-device claim.

Failure coverage: absent confirmation, foreign/stale/unbound object, person overlap, source/frame
mismatch, untrusted extra JPEG field rejected, unauthorized image access, wrong-name/missing
strong confirmation, altered authenticated metadata, expiry denial and transaction-audit rollback
with no leaked file/reference. Simulated unlink failure leaves access denied and entity reference
removed; a later successful cleanup removes ciphertext. No actual personal data was processed.

Benchmark python -m mnemos.reference_benchmark: 50 synthetic 128px crops, isolated SQLite and
files under runtime/tmp, removed at completion. p95 crop 0.100ms, store+audit 1.843ms,
read+audit 1.171ms, revoke/purge+audit 2.317ms. runtime/exports/reference-benchmark.json.
These are overhead timings, not quality, similarity, identity accuracy or full pipeline latency.

Core HTTP surface now implements explicit crop save, authenticated no-store image read, strong
revocation and sanitized retention-worker status. Dashboard reference controls and live loopback
verification remain next work; no UI or live sample acceptance is claimed from backend tests.
Retention timestamps must be timezone-aware; no silent reference deadline expansion is allowed.

T017 remains partial, all epic/milestone exit criteria unproven. ADR-026 records filesystem/DB
crash orphan and deletion/backup limitations; representative physical quality and matching remain.

Additional private-file/lost-key regression: insecure file denies access, missing original key
denies read and refuses new store without generating a replacement; restoring exact original
bytes and 0600 recovers the reference. The latest raw reference frame expires after two seconds
of source inactivity, independently of the five-minute compressed rolling buffer.

Final idle-frame regression passes: the expiry worker drops the raw reference frame after
two seconds without source data. Final suite 110 passed/no skips. Live core retention status
reports no error, PostgreSQL alembic_version=0004_object_references and object_references exists.
The live crop-save roundtrip remains pending; this readiness check does not substitute for it.

Dashboard integration follow-up:
- Production TypeScript/Vite build passes (35 modules). Save-current-crop controls require bound
  track, explicit future local deadline and unchecked object-only confirmation. Metadata list
  is owner-only/no-store, active and bounded to 20; no storage paths/crypto envelopes returned.
- Separate synthetic 5181 server: default unchecked save disables submission; explicit face-free
  synthetic crop saved with chosen deadline. Gallery displayed crop and deadline, wrong-name
  revocation stayed disabled; final irreversible browser delete was not submitted. Stop preserves
  the explicit reference; reload/reconnect retrieves it; Disconnect clears token/gallery/image.
  Screenshot runtime/exports/reference-dashboard.jpg, exclusively synthetic state.
- Preview fetches are authenticated no-store with memory-only blob URLs. Abort and generation
  guards prevent stale responses after disconnect/metadata invalidation; lazy display avoids
  loading all stored images, and local expiry checks hide an expired selected preview.
- python -m mnemos.reference_http_verify: actual HTTP over temporary loopback port, actual isolated
  PostgreSQL test_reference_http_* schema, generated source/detector. Save 16.81ms, decode confirms
  only 96x96 crop of a 128x128 source, encrypted private file verified, persistence after Stop,
  revoked read 403/404, physical cleanup 605.82ms. Seven ID-only audits without name, including
  three reads. Temporary schema/files/key/server cleaned. runtime/exports/reference-http.json.
- Repeated synthetic benchmark: p95 crop 0.089ms, store+audit 1.662ms, read+audit 1.176ms,
  retire/purge 2.365ms. Scope unchanged; no representative quality/identity accuracy claim.

Earlier pending dashboard and live-HTTP reference items above are superseded by this evidence.
Authorized person sample acquisition, representative physical quality/matching and full integrated
acceptance remain pending; T017 stays In Progress. No extra task/epic/milestone declared Done.

Final follow-up checks: 110 tests pass again/no skips, Ruff/format/strict mypy (49 sources), eight
mirror hashes and replay pass. Production web build passed; all five Drive modified timestamps
match the mirror. The synthetic 5181 server was stopped normally after browser Disconnect;
its generated fixture remains local. Installed core was confirmed idle before restart with the
new metadata-list API; no active sensor session was interrupted.
