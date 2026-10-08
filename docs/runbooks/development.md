# Development and verification

From repository root:

```sh
export UV_CACHE_DIR="$PWD/runtime/cache/uv"
export UV_PYTHON_INSTALL_DIR="$PWD/runtime/python"
export UV_PROJECT_ENVIRONMENT="$PWD/runtime/core-venv"
export TMPDIR="$PWD/runtime/tmp"
uv python install 3.11
uv sync --locked --extra dev --extra media --python 3.11
docker compose up -d postgres
runtime/core-venv/bin/alembic upgrade head
scripts/check
MNEMOS_TEST_POSTGRES='postgresql+psycopg://mnemos:mnemos@127.0.0.1:5432/mnemos' runtime/core-venv/bin/python -m pytest tests/test_postgres.py -q
```

If uv is not installed, bootstrap it into runtime/venv with pip; no global install is needed.
DB binds only loopback. Default DB credentials are for the isolated local development service.
Configure a random `MNEMOS_OWNER_TOKEN` with at least 32 characters in your process environment.
Do not commit or print the token. Then run:

```sh
runtime/core-venv/bin/uvicorn mnemos.api:create_app --factory --host 127.0.0.1 --port 8000
```

`/health` is non-sensitive; registry/readiness/schema endpoints require owner Bearer auth.
No camera/mic, biometric collection, raw recording or cloud calls start automatically.
Entity API supports authorized create/read/update; deletion must be integrated with strong
confirmation, audit and biometric revocation before exposing a delete endpoint.

Canonical Drive sync: fetch the five files using the connected Google Drive tool. Materialize
a transient JSON map under runtime/tmp keyed by Drive ID, with content, modified_time and url.
`python -m mnemos.docs_sync pull --snapshot runtime/tmp/drive-snapshot.json` preflights all
files, rejects local/remote conflicts and records SHA256/version/time. `status` without a
snapshot reports remote-unchecked; `verify` only verifies cached bytes. `push` requires explicit
human intent plus a configured live OAuth transport. Native Docs edits preserve paragraph structure
with revision guards; Sheets patches only changed RAW cells. Post-write readback must verify.
No Drive upload has been performed. See scripts/docs-sync/README.md for limits and commands. Local progress lives under docs/plan,
separate from canonical requirements; default sync never writes Drive.

Real model smoke and M1 measurements after installing pinned weights from docs/models.json:

```sh
MNEMOS_TEST_MODELS=1 runtime/core-venv/bin/python -m pytest tests/test_vision.py -q
runtime/core-venv/bin/python -m mnemos.vision_benchmark
```

Model loading is lazy and verifies hashes/license before execution. Benchmark uses blank pixels;
positive/negative accuracy fixtures are still required. Native camera/mic source construction
requires an explicit device_authorized flag; OS permission grants must also exist. Neither
source writes media to disk or starts from API import. Shared SourceClock aligns file A/V replay.

Reproduce the installed model cache with `runtime/core-venv/bin/python -m mnemos.download_models`.
The downloader accepts only the registered official model origin, checks byte length and SHA256
before atomic replacement, and retains an existing file on failed/corrupt download. No hidden
model downloads occur during inference. Network failure leaves inference explicitly unavailable.

Local dashboard:

```sh
pnpm --dir apps/web install --frozen-lockfile --store-dir "$PWD/runtime/cache/pnpm"
pnpm --dir apps/web build
scripts/dev
# In another terminal:
pnpm --dir apps/web dev
```

Open http://127.0.0.1:5173. scripts/dev creates a local owner token under
runtime/data/security/owner-token with restrictive permissions and loads it without printing it.
Retrieve it privately for the dashboard; never paste it into chat or source control. The dashboard
keeps it only in memory. Disconnect confirms sensor stop before clearing token/catalog; if stop
fails, the connection remains available for recovery. Both servers bind loopback. Sensor use
requires separate camera/microphone consent and OS permissions; no persistent recording starts. Stop foreground servers with Ctrl+C.

Actual perception harness: `runtime/core-venv/bin/python -m mnemos.perception_replay`.
Its public-domain fixture and provenance are committed under runtime/datasets/public; generated
replay AVI/tone and report remain disposable under runtime. It checks detector/face/tracker and
audio-clock integration, not ASR quality or recognition of enrolled people.

Continuous replay is available after generating the perception fixture. Connect the dashboard,
then select “Avvia replay di verifica”; no hardware permission is requested. Owner-only
/capture/start, /capture/status, /capture/frame and /capture/stop provide the same controls.
One active source session is allowed. Preview responses use no-store; queues retain at most
2 raw frames, audio/video circular buffers remain in process and are cleared on stop/failure/EOF.
Native sensor controls are an explicit user action; implementation tests use replay only.
Closing the browser does not itself stop the core: use Stop sensori or Disconnect first.

Temporal reminders: apply `runtime/core-venv/bin/alembic upgrade head`, then restart the core.
In the dashboard, enter reminder text and a local date/time; the browser sends an aware UTC
deadline. The local inbox updates after the one-second scheduler tick. If the core was stopped,
overdue pending reminders deliver on restart. Scheduler/database failures are visible in the
panel. Delivery is retained for later authenticated reads; it does not require OS notification
permissions. No external message is sent. For reproducible isolated measurements run
`runtime/core-venv/bin/python -m mnemos.scheduler_benchmark`.

Local speech runtime (existing macOS CMake/Xcode toolchain required):

```sh
runtime/core-venv/bin/python -m mnemos.download_models
runtime/core-venv/bin/python -m mnemos.build_speech
runtime/core-venv/bin/python -m mnemos.speech_fixture
MNEMOS_TEST_SPEECH=1 runtime/core-venv/bin/python -m pytest tests/test_speech.py -q
runtime/core-venv/bin/python -m mnemos.speech_benchmark
```

The fixture generator uses installed Alice/Samantha voices and validates nonempty 16kHz mono
PCM16; it does not use the microphone or play audio. Missing/unavailable voices produce a
verification failure rather than a fabricated sample. Tests/build need local native services
and may require sandbox authorization in Codex. All source/model/build/fixture output is contained.
StreamingSpeech is connected to the core's capture worker and dashboard. Select “Avvia replay
vocale” to test without device permissions; the fixture includes a silent tail for observing
final text before EOF cleanup. Native microphone consent includes local transcription. The API
exposes transcribe/language options; speech-replay requires camera=false, microphone=true.
A starting phase prepares models before opening sources and resetting their shared clock.
Text is volatile, expires within 300s, is capped at 50 utterance revisions, and clears on stop,
failure or EOF. One bounded 128-chunk audio queue drops oldest packets; gaps reset speech state
and retract unfinished partial text. This does not grant voice-command authority.

### Reviewed object-name proposals

While native consenting capture is active, eligible final IT/EN transcripts can show a temporary
name suggestion. Correct it and explicitly confirm “Registra nome”, or ignore it. An anonymous
speaker cannot write the registry. The name catalog does not yet establish physical identity.
Stop/end-of-source clears unconfirmed suggestions. A mutation already explicitly confirmed
can finish independently during stop; refresh the catalog after an interrupted HTTP response.

Reproduce narrow routing benchmark: `python -m mnemos.voice_enrollment_benchmark`.
Opt-in real pipeline check with the idle local development core and generated synthetic fixture:
`python -m mnemos.voice_enrollment_verify`. It uses only fixed speech replay, creates/removes
one unique synthetic registry fixture, reads the local owner token in memory, and reports only
aggregate evidence. Never alter it to use personal speech/data without the consent flow.
See verification/voice-enrollment.md and ADR-023 for exact scope and remaining work.

Object association: register an object manually or through reviewed voice proposal, start an
explicitly permitted video source, then choose its numbered overlay track and catalog name under
Associa un oggetto del feed. Check the confirmation and submit. The name is an owner assertion
for this uninterrupted track; detector percentage is not identity confidence. Missing/stale tracks,
people/face tracks and other-owner entities reject. First missed detection or stop clears binding;
reference/matching work is still required for automatic recognition on reappearance.
