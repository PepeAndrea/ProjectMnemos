# DATA_LAYOUT.md

| Path | Data | Persistent? | Default Retention | Safe to delete? |
|---|---|---|---|---|
| runtime/data/postgres/ | DB | Yes | explicit | No |
| runtime/media/audio/ | persisted audio | policy | policy | Caution |
| runtime/media/video/ | persisted video | policy | policy | Caution |
| runtime/media/keyframes/ | keyframes | Yes | policy | Caution |
| runtime/media/evidence/ | evidence | Yes | audit/policy | Caution |
| runtime/models/ | model weights | cache-like | until removed | Yes/re-download |
| runtime/cache/* | caches | No | cache | Yes |
| runtime/logs/ | telemetry | bounded | configurable | Yes |
| runtime/tmp/ | buffers/temp | No | minutes/session | Yes |
| runtime/datasets/ | replay fixtures | Yes | explicit | If backed up |
| runtime/exports/ | user exports | Yes | user | If copied elsewhere |

Rolling buffers belong in runtime/tmp or memory-backed equivalents, max 5 minutes experimentally.
Destructive purge must enumerate what will be deleted and require explicit confirmation.

## Implemented foundation locations

- runtime/python/: uv-managed CPython 3.11, disposable after removing dependent environments.
- runtime/core-venv/: locked official Python 3.11 environment, disposable/reproducible via uv.lock.
- runtime/venv/: temporary Python 3.14 bootstrap environment containing uv, disposable when no longer needed.
- runtime/cache/{pip,uv,pytest,ruff,mypy}/: contained build, dependency and check caches.
- runtime/tmp/drive-snapshot.json: temporary canonical content fetched with Drive connector;
  keep local, remove after sync, never publish as user data.
- runtime/datasets/synthetic/: generated non-personal tone.wav and PPM frames, regenerable.
- runtime/exports/{foundation-benchmark,resource-benchmark}.json: non-personal benchmark telemetry.
- In-process RollingBuffer: no filesystem persistence, duration <=300s and explicit byte ceiling.
- docs/plan/progress.json: versioned implementation evidence ledger; not the canonical Drive plan.
- packages/contracts/: versioned generated JSON Schemas, source is apps/core/mnemos/domain.py.

Default environment redirects HF_HOME, TORCH_HOME, XDG_CACHE_HOME, TMPDIR and UV_CACHE_DIR.
RuntimeLayout rejects parent traversal, absolute escapes and symlinks leading outside runtime.
Project bootstrap does not authorize destructive purge, record real conversations, or persist
biometric templates. No media persistence endpoint exists yet.

- runtime/models/opencv/: pinned YOLOX-S and YuNet ONNX weights, disposable with checked re-download. Hash/license records live in docs/models.json.
- runtime/tmp/licenses/: transient fetched upstream metadata; retained applicable license copies in docs/licenses.
- runtime/exports/vision-benchmark.json: safe model load/inference timing and process peak RSS.

- runtime/datasets/public/: registered reusable public-domain regression photo plus source/hash metadata; no biometric enrollment data.
- runtime/datasets/perception-replay/: generated four-frame video/tone from registered inputs, regenerable.
- runtime/web-dist/: production React bundle, generated and disposable.
- runtime/cache/{pnpm,vite}/: frontend dependency/build caches.
- runtime/data/security/owner-token: local bearer secret, mode 0600 within 0700 directory; do not log/export it. Rotation currently requires replacing it while core is stopped.

- Continuous capture: in-process two-frame queue, 64MiB sampled JPEG / 16MiB PCM circular buffers, <=300s. Stop/failure/EOF clears raw media; anonymous lifecycle metadata is capped at 100 events and cleared on stop. No disk recordings.
- runtime/exports/capture-http-verification.json: non-personal loopback replay performance/status evidence.
- runtime/tmp/docs-sync-*/: transient staging directory, automatically removed after commit/rollback.

- PostgreSQL reminders/notifications/local_action_audit: explicit persistent prospective memory,
one-shot deadlines, local inbox and policy execution audit; no raw A/V or biometric templates.
- runtime/exports/{scheduler-benchmark,reminder-http-verification}.json: non-personal performance
evidence; runtime/tmp/scheduler-benchmark-*/ is an isolated temporary SQLite DB removed at exit.
- PostgreSQL test_scheduler_* schemas are isolated disposable concurrency fixtures, dropped by
the test cleanup; they never process installation reminders.

Capture checks idle buffer expiration every 100ms, including audio-only sessions; each buffer
also caps 20,000 chunks to bound object overhead, and skips zero-byte payloads.

- runtime/tools/whisper.cpp-<revision>/: verified official native source, disposable/re-downloadable.
- runtime/tools/whisper-build/: CMake outputs, native bridge/dylibs, artifact hash manifest;
  disposable/reproducible with python -m mnemos.build_speech. No global install target is used.
- runtime/models/whisper/: pinned Whisper Tiny/Base and Silero ggml files, hashed/license-gated.
- runtime/datasets/speech-synthetic/: locally synthesized IT/EN PCM plus source/voice/reference/hash
  metadata. Not a recording of a person, not committed/distributed; regenerate with speech_fixture.
- runtime/tmp/{asr-spike,whisper-source.tar.gz,speech-*.aiff}: disposable metadata/source staging and
  synthetic-generation scratch. Active inference passes PCM in memory and writes no WAV or text.
- runtime/exports/speech-benchmark.json: non-private aggregate WER, timing and peak RSS on synthetic
  fixtures; no inferred user identity. ASR segments/partials remain caller-owned volatile values.

- In-process speech capture: 128-chunk PCM work queue, <=15s VAD segment/pre-roll, <=50 volatile
  utterance revisions expiring within 300s. No transcript/audio DB writes occur automatically;
  stop, source failure and EOF clear all public queues/media/text and evict model contexts.
- runtime/datasets/speech-synthetic/stream.wav: generated English fixture plus three-second silent
  tail, not committed; regenerated by speech_fixture. No real-person recording.
- runtime/exports/speech-capture-http.json: non-private latency/drop/cleanup evidence.
- runtime/tmp/ui-speech-test.db: disposable isolated browser-test database, only synthetic owner
  authentication and empty/synthetic test state; never used by the installed core.

- PostgreSQL local_action_audit also records explicit manual entity create/update decisions,
  actor/entity IDs and execution status atomically with the mutation; entity content is not
  duplicated there. Generic person enrollment is blocked pending verified consent.
- runtime/exports/registry-benchmark.json and runtime/tmp/registry-benchmark-*/: synthetic
  registry timings and disposable isolated SQLite database (removed on completion).
- PostgreSQL test_registry_* schemas: isolated synthetic fixtures dropped at test cleanup.

- Entity deletion audit retains only actor/action/entity IDs and decision/status, not deleted
  entity names or attributes. Entities with evidence/biometric/inbound links require dedicated
  revocation and are rejected by generic delete.
- runtime/exports/{registry-http.json,registry-dashboard.jpg}: aggregate live HTTP evidence
  and screenshot of isolated synthetic dashboard; runtime/tmp/ui-registry-test.{py,db} are
  disposable fixtures, never installation state.

- In-process VoiceEnrollmentInbox: <=50 proposed names/action IDs and <=200 dedup IDs;
  five-minute maximum from final utterance timestamp. Cleared on stop/failure/global EOF.
  No anonymous speaker identity, full transcript or audio is persisted by suggestion generation.
- Explicit reviewed catalog creation stores the corrected name with human owner provenance;
  local_action_audit links the original proposal UUID only. In-flight confirmed DB writes can
  complete during sensor stop without reviving volatile capture state.
- runtime/exports/voice-enrollment-{benchmark,http}.json: non-private routing/timing/audit-count
  evidence. runtime/exports/voice-enrollment-dashboard.jpg: isolated synthetic browser state.
- runtime/tmp/ui-voice-enrollment-test.{py,db}: disposable synthetic provider/SQLite dashboard
  verification, with native capture disabled. Not the installation's registry or bearer token.

- PostgreSQL person_consents: owner-attested permission scopes, deadline, policy version/status,
  minimal IDs/dates retained after revoke/expiry. Name stays in the authorized Entity row only.
- PostgreSQL biometric_templates: provider/dimension metadata plus AESGCM ciphertext and nonce;
  no raw image/audio. Server-internal vectors are scope/expiry/owner gated, no HTTP vector API.
- runtime/data/security/biometric-key: lazy 32-byte key outside DB, regular owner-only 0600 file,
  parent 0700. No key generated for installed production state during synthetic verification.
  Key loss with existing ciphertext fails closed; never regenerate as a recovery procedure.
- runtime/tmp/pytest/: configured pytest temporary files/databases/keys; generated fixtures are
  contained. test_biometrics_* PostgreSQL schemas are isolated and dropped after checks.
- runtime/exports/{biometric-benchmark,person-enrollment-http}.json: aggregate synthetic timings
  and checks, no raw vectors/keys. person-consent-dashboard.jpg includes consent metadata from
  the isolated verification UI (synthetic entry plus manually entered record), kept local.
- runtime/tmp/ui-registry-test.db: retained isolated browser fixture plus manually entered consent
  metadata; not production enrollment. No real biometric samples were captured. Do not silently
  purge manual additions. The test server remains loopback-only and separate from installation DB.
- Default /Users/andreapepe/.cache/uv received metadata from one unredirected dependency resolution;
  subsequent sync uses runtime/cache/uv. This exception is recorded rather than deleting shared cache.
- Revocation removes active Entity/template rows with audit atomically. It does not prove secure
  erasure of WAL/OS caches/future backups; backup policy and gallery eviction remain planned work.

- CaptureSession visible_tracks/track_bindings/claim tokens: volatile <=128 tracks. Current
  object associations disappear at first missed detection, stop, failure or global EOF. They do
  not create durable identity for unknown people or copy/store reference pixels.
- local_action_audit track_bind: confirmed owner action linking session/track/entity IDs only,
  without name, boxes, source pixels/audio. It records authorization, not perpetual recognition.
- runtime/tmp/ui-track-binding-test.{py,db}: separate synthetic-only 5181 browser fixture;
  not the 5180 manually edited fixture or installed registry. Native modes reject.
- runtime/exports/track-binding-{benchmark.json,dashboard.jpg}: synthetic coordination timings
  and synthetic UI screenshot; runtime/tmp/track-binding-* temporary benchmark DB removed at exit.
- PostgreSQL test_track_binding_*: isolated synthetic audit tests, schemas dropped by cleanup.

- CaptureSession.reference_frame: one latest normalized raw frame, volatile/bounded by source
  dimensions, cleared on stop/failure/EOF or after two seconds without a fresh frame. Only explicit owner-bound crop requests retain a selected
  snapshot for encoding; general buffer/media remain non-persistent.
- runtime/media/evidence/object-references/<UUID>.enc: AESGCM nonce+ciphertext of explicit object
  JPEG crop; no public static media. Folder 0700/file 0600, 20 references/entity, 512 files/64MiB
  global per-core budget, 2MiB JPEG. Detected person/face overlaps reject this non-biometric route.
- runtime/data/security/reference-key: separate lazy 32-byte owner-only file key; missing with
  existing metadata/files fails closed. No production key acquired during these synthetic checks.
- PostgreSQL object_references: owner/entity ID, source provenance, explicit deadline, byte count
  and active/pending-deletion state; no JPEG/name in row. Entity.reference_ids are transactional.
- Revocation removes access/link before filesystem cleanup; unlink failure retains deletion
  tombstone for retry. Expired reads deny before worker cleanup. ID-only local_action_audit covers
  store/read/delete/expire. File/DB crash orphans remain inaccessible but need later reconciliation;
  no secure erasure of OS caches/backups claimed.
- runtime/exports/voice-person-http.json: aggregate actual Whisper/HTTP/PostgreSQL synthetic
  person registration timings and consent/revoke checks; no names, transcript or samples.
  Reviewed person consent audit links only proposal UUID; verifier removes its own synthetic rows.
- runtime/tmp/ui-voice-person-test{.py,.db,/runtime}: isolated synthetic UI fixture and
  server source; no production biometric data/key. Server stopped after verification.
- runtime/exports/voice-person-dashboard.jpg: screenshot of corrected synthetic person
  name and face-only consent after Stop/reload; no real participant or private owner token.
- object_references.payload.provenance.quality: versioned crop dimensions and measured
  contrast/luma/detail/clipping warnings, bound to encrypted-envelope AAD, no identity
  confidence. Legacy references have no quality. Entity-bound HMAC content_tag remains
  internal metadata, never an audit label or public listing field.
- runtime/exports/reference-quality-benchmark.json and reference-quality-dashboard.jpg:
  synthetic timings/diagnostics/UI proof. runtime/tmp/ui-quality-test* contains only
  isolated synthetic SQLite/key/crop/server fixtures; server stopped after review.
- runtime/exports/reference-benchmark.json: aggregate synthetic timings. runtime/tmp/reference-
  benchmark-* contains temporary synthetic keys/files/SQLite removed after run. PostgreSQL
  test_references_* isolated schemas are dropped; pytest sample media stays runtime/tmp/pytest.

- Reference gallery: one lazily fetched authenticated no-store JPEG held as memory-only browser
  blob URL, revoked on hide/expiry/object or auth change; no localStorage or persistent browser
  credential/image export introduced. Preview cache invalidation does not promise OS memory erase.
- runtime/tmp/ui-reference-test/runtime/{media/evidence/object-references,data/security}: synthetic
  browser verification crop/key only; separate from production media and manually edited 5180 DB.
- runtime/exports/{reference-http.json,reference-dashboard.jpg}: real orchestration checks over
  synthetic content and synthetic gallery screenshot; no real subject or native sensor acquired.
- runtime/tmp/reference-http-*/: synthetic HTTP test root, temporary keys/files removed at exit.
  PostgreSQL test_reference_http_* isolated schemas are dropped; random loopback test server stops.

- PostgreSQL face_references (migration 0005): separate owner/person/image metadata, expiry,
  active/pending-deletion state and consent UUID bound to encrypted-envelope provenance.
  Does not add face IDs to generic Entity.reference_ids. No name or JPEG in table/audit.
- runtime/media/evidence/face-references/<UUID>.enc and runtime/data/security/face-reference-key:
  independent bounded AES-GCM face image store, folder 0700/files 0600, lazy separate key.
  Active face consent checked on every acquisition/list/read; revocation denies immediately,
  physical cleanup asynchronous with retry. No production face key/sample acquired in tests.
- runtime/exports/face-reference-{http,benchmark}.json: aggregate generated-pixel checks only.
  Temporary face-reference test roots and isolated PostgreSQL schemas removed after verification.
- Face gallery: separate memory-only authenticated blob, cleared on person/consent/auth changes;
  no persistent browser token/image storage. Isolated browser save/preview/Stop/reload/Disconnect verified.
- runtime/tmp/ui-face-reference-test* and runtime/exports/face-reference-dashboard.jpg: synthetic
  SQLite/person/key/image/server fixture and proof; no real face. Loopback test server stopped.

- Five-point face geometry: bounded local detector/tracker state, omitted from public capture
  payloads. Acquisition map cleared on track loss, stale frame, Stop/failure. Consented image
  quality stores only derived uncalibrated detail/geometry; no raw points or names in audit.
- runtime/datasets/face-synthetic/{fictional-frontal-v1.png,manifest.json,README.md}: one
  wholly AI-generated fictional portrait, pinned hash/full prompt, no real participant. Original
  built-in imagegen artifact remains in Codex generated_images; project uses its own copy.
- runtime/exports/face-quality-{benchmark,replay}.json: generated diagnostics/costs and one
  positive real-YuNet synthetic replay; no representative quality/recognition calibration.

- runtime/tmp/ui-face-quality-test* and runtime/exports/face-quality-dashboard.jpg: isolated
  synthetic SQLite/person/crop/key/server fixtures and dashboard proof with actual local YuNet.
  No production face enrollment/key or native permissions; loopback 5185 server stopped.

- Capture diagnostics: volatile fixed error_code, worker_active and source_cleanup_failed;
  no raw driver exception, device name, path, media or transcript persisted. First failure
  retained during secondary cleanup; Stop clears private media even if a worker remains live.
- runtime/exports/source-failure-{http,benchmark}.json and source-{failure,recovery}-dashboard.jpg:
  aggregate simulated source/worker measurements and UI proof, no native sensor or real media.
- runtime/tmp/ui-source-failure-test*: isolated synthetic SQLite/server fixture; no production
  DB/token or image/biometric key. HTTP verifier temporary source-failure-http-* roots removed.

- Native webcam discovery (ADR-033) probes at most five OpenCV indices during an explicitly
  consented start. Candidate handles and the selected device are session-local and volatile;
  manual index choice stays in dashboard memory for the current page/session; no device
  identifiers or camera frames from the probe are persisted.

## Temporary person names and Italian speech (2026-10-09)

Session face display names and utterance dedup IDs remain in process memory only; Stop/failure,
track loss or stale frames clear names. No database identity, biometric reference or media is
created by annotation. `runtime/datasets/session-names-synthetic/` holds regenerated local
synthetic IT/EN speech, manifests/hashes and retained low-confidence negative fixtures.
`runtime/datasets/speech-synthetic/stream-it.wav` adds the default Italian paced replay.
`runtime/exports/session-names-replay.json`, `session-names-italian-spike.json` and
`session-names-dashboard.jpg` contain synthetic verification evidence. Optional explicitly
consented native CLI runs write only aggregates to `runtime/exports/native-acceptance.json`;
no actual native report has been generated yet.

Additional synthetic evidence: `runtime/exports/session-names-automatic-italian.jpg` verifies
Italian automatic annotation; `runtime/exports/italian-default-http.json` records aggregate
actual-core Italian replay and Stop checks. Isolated UI server 5187 was stopped after verification.
