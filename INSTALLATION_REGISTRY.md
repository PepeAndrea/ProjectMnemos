# Installation registry — 2026-10-08

Only the installed rows below are present; candidates have no downloaded weights or approved
weight-license claim. Python dependencies and hashes are locked in uv.lock. No global package
installation was introduced. Hardware verified: Apple M1, 8,589,934,592 bytes RAM, macOS arm64.

| Component | Version / hash | Purpose | Method / location | Approx size | Required | License / removal |
|---|---|---|---|---:|---|---|
| Docker Desktop / CLI | CLI 29.8.0, pre-existing | DB infra | /Applications/Docker.app, Docker-managed image store outside repo | pre-existing | DB | Vendor terms; stop project via docker compose down; do not uninstall shared Docker |
| PostgreSQL + pgvector | pg17 image sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d | DB/vector | Docker, data runtime/data/postgres; loopback 5432 | image 625MiB | yes | PostgreSQL/pgvector licenses; compose down, remove image only if unshared; data requires confirmed purge |
| Python | CPython 3.11.17 | official core runtime | uv managed runtime/python | 75MiB | yes | PSF; remove project envs then managed runtime/python |
| Python bootstrap | pre-existing 3.14.7 | install uv only | runtime/venv | 221MiB | bootstrap | PSF + package licenses; remove bootstrap env when uv is otherwise available |
| uv | 0.12.23 | lock/install | pip inside runtime/venv, cache runtime/cache/uv | 17MiB wheel | yes | Package distribution terms; remove bootstrap env/cache |
| Core dependencies | exact versions/hashes uv.lock | API/domain/database | uv sync, runtime/core-venv | ~200MiB including media | yes | FastAPI/Pydantic/SQLAlchemy MIT; Uvicorn BSD-3-Clause; psycopg LGPL-3.0-only; transitive terms apply; remove env |
| OpenCV headless | 4.14.0.94 | local/file video + later vision | media extra, runtime/core-venv | 44MiB wheel | media | Apache-2.0 package metadata, bundled dependency terms apply; remove env |
| NumPy | 2.4.6 | media arrays | media extra, runtime/core-venv | 5MiB wheel | media | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 metadata; remove env |
| sounddevice | 0.5.6 | native PCM capture | media extra, runtime/core-venv | small | mic | MIT package, bundled PortAudio terms apply; remove env |
| Node.js | pre-existing 22.14.0 | future React web | ~/.nvm/versions/node/v22.14.0 | pre-existing | web | MIT; do not remove shared installation |
| EmbeddingGemma 2 | not installed | multimodal candidate | planned runtime/models | unknown | benchmark | weight/model availability and license must be verified before download/use |
| YOLOX-S / YuNet | pinned OpenCV Zoo commit 47534e27c9851bb1128ccc0102f1145e27f23f98; hashes docs/models.json | object/face detection | runtime/models/opencv, official raw/LFS downloads | 34.2MiB / 227KiB | baseline | Apache-2.0 / MIT, code AND weights directory licenses; copies docs/licenses; delete model files to remove |
| SFace | not installed | face recognition candidate | planned runtime/models | unknown | perception | Verify code AND weights before enabling |
| LAN certificate / CA | not provisioned | HTTPS phone | planned runtime security dirs + trust store | unknown | phone | Explicit trust setup and removal must be recorded |

Project also created one Docker network and mnemos-postgres-1 container; `docker compose down`
removes these without deleting bind-mounted data. Pip/uv build/download caches (~229MiB at
initial setup) are under runtime/cache; transient build directories are under runtime/tmp.
Editable Python package metadata (`apps/core/*.egg-info`) is disposable ignored build metadata.
No sensor permissions, real biometric enrollment, CA trust or cloud credentials were configured.

Web dependencies: React/ReactDOM 19.3.0, Vite 7.3.7, TypeScript 5.9.3, React plugin 5.2.0,
pnpm 11.25.0 (pre-existing bundled). Exact versions/integrity in apps/web/pnpm-lock.yaml.
Installed apps/web/node_modules with store runtime/cache/pnpm; only esbuild build hook is
allowed by apps/web/pnpm-workspace.yaml. Build output runtime/web-dist, cache runtime/cache/vite.
Remove node_modules/cache/build to uninstall project web dependencies, leaving shared Node/pnpm.

Public replay input: NASA photograph via scikit-image v0.24.0, 791555 bytes, SHA256
88431cd9653ccd539741b555fb0a46b61558b301d4110412b5bc28b5e3ea6cb5. Public-domain
provenance documented in runtime/datasets/public/astronaut-source.json; detection only.
No scikit-image or additional scientific runtime was installed.

Continuous capture and native Drive/Docs/Sheets sync use the existing locked media stack and
Python standard library; no additional package or OAuth credential was installed. Both model
providers unload after source completion/stop. Physical sensor permission remains unconfigured.

Temporal scheduler uses asyncio/SQLAlchemy and the existing PostgreSQL service. Additive migration
0002_temporal_reminders creates three project tables and a deadline index. No new package,
daemon, notification permission or external service was installed. Schema rollback is destructive
to stored reminders/inbox/audit and must not be used as routine cleanup of user data.

Speech runtime added on 2026-10-08:

| Component | Version / hash | Purpose | Location / size | License / removal |
|---|---|---|---|---|
| whisper.cpp | tag v1.9.5, commit d1be6fde11ac6e0407606b4e42fe72d34add8037; archive SHA docs/native-tools.json | native ASR + VAD | runtime/tools/whisper.cpp-*, source ~47MiB; runtime/tools/whisper-build ~49MiB | MIT, copy docs/licenses/whisper-cpp-MIT.txt; remove project source/build to uninstall |
| Whisper Tiny / Base multilingual | HF revision 5359861c739e955e79d9a303bcbc70fb988958b1, hashes docs/models.json | ASR baseline/comparison | runtime/models/whisper, ~74.1MiB /141.1MiB | MIT model-card metadata; pinned primary license sources in manifest; remove individual weight files |
| Silero VAD v6.2.0 ggml | HF revision 9ffd54a1e1ee413ddf265af9913beaf518d1639b, SHA docs/models.json | speech activity | runtime/models/whisper, ~0.844MiB | MIT model-card metadata; pinned source in manifest; remove weight file |
| CMake | pre-existing 4.4.3 | native reproducible build | /opt/homebrew/bin/cmake | upstream terms; do not remove shared tool |
| Apple C++ / Accelerate / Metal | pre-existing AppleClang 21.0.0.21000101, Xcode SDK | CPU/GPU native execution | existing system/Xcode | Apple SDK/system terms; no system install or removal performed |
| Alice / Samantha speech voices | pre-existing macOS voices | synthetic IT/EN fixture generation | system voices; generated PCM only under runtime | system terms; generated audio not redistributed or committed |

The bridge is project source under apps/core/native and builds only into runtime. Runtime dylib
hashes plus bridge-source/revision checks gate loading. Metal library compilation artifacts are
embedded in the contained build; driver-managed shader caches are OS-managed and cannot be
redirected by this integration. No additional Python ML framework, recording grant or cloud
credential was installed. Tiny+Metal is a provisional latency baseline; accuracy is uncalibrated.

Continuous speech integration reuses the installed native runtime and locked Python/web stack.
The bridge now supports observable/sticky native cancellation and was recompiled with the same
contained build recipe; artifact/source hashes updated in runtime/tools/whisper-build/manifest.json.
No new package, permission or external service was added. The isolated port-5180 browser test
server is temporary and is stopped after verification; it rejects native sensor mode.

Registry policy integration (ADR-022): reuses existing Python/SQLAlchemy/PolicyEngine and
0002 local_action_audit table; no package, model, system install or schema migration added.

Voice proposal/review integration (ADR-023): uses existing stdlib/ASR/PolicyEngine/SQLAlchemy
and React; no new package, model, native install or schema migration. Local bounded grammar
makes zero cloud calls. Biometric enrollment/voice identification are not implied by this install.

Consent vault (ADR-024), added 2026-10-08: cryptography 50.0.2 in runtime/core-venv, locked in
uv.lock, PyPI wheel with bundled OpenSSL 4.0.3 (29 Sep 2026). Installed license expression:
Apache-2.0 OR BSD-3-Clause; no system OpenSSL install. Remove via project dependency/environment
rebuild only after preserving required encrypted data/key recovery. Migration 0003_person_consent
adds consent and encrypted-template tables. No production biometric key/template was acquired.
One initial `uv add --no-sync` resolution omitted UV_CACHE_DIR and used the default
/Users/andreapepe/.cache/uv for dependency metadata. This was an avoidable containment exception;
actual environment sync used runtime/cache/uv and runtime/tmp. Shared outside cache was not deleted.

Session object association (ADR-025): reuses installed React/Python/SQLAlchemy/PolicyEngine and
existing audit table. No package, model, schema or OS permission added. Temporary loopback 5181
verification server uses only synthetic pixels/detection and an isolated SQLite DB; stopped after
verification. Existing manually edited 5180 fixture and installation PostgreSQL remain separate.

Explicit object-reference media (ADR-026): no new dependency or model; existing OpenCV JPEG,
cryptography/SQLAlchemy/PolicyEngine. Additive migration 0004_object_references creates metadata
and expiry/entity indices. Private reference-key is lazy, separate from biometric-key; no
production key/image created by synthetic tests. Reference benchmarks use isolated runtime/tmp
keys/files/SQLite; actual PostgreSQL test schemas are dropped at cleanup. Downgrade is destructive
and must not be used as routine cleanup of enrolled data.

Object-reference dashboard/gallery uses existing React/TypeScript/web stack, no new package.
Voice-reviewed person registration reuses the installed ASR/API/consent/React stack;
no new dependency, model, migration or sensor permission. Real HTTP verification uses
only synthetic corrected person metadata and removes its own fixture rows.
Isolated browser server on loopback 5182 rejected native modes and used synthetic
audio/proposal plus SQLite under runtime/tmp. Stopped after browser verification.
Reference quality/duplicate guard (ADR-029) reuses OpenCV/NumPy/stdlib HMAC and the existing
private reference key. JSON metadata only; no new package/model/schema migration. Browser
5183 used an isolated runtime/tmp fixture with native modes disabled; test server stopped.
Actual multiview HTTP test uses an isolated PostgreSQL schema/private root cleaned afterward.
Live reference_http_verify uses existing Uvicorn/OpenCV/PostgreSQL in an isolated schema and
random loopback port, with native modes disabled. Temporary source/keys/media/server cleaned on
successful verification. Browser 5181 storage is redirected to runtime/tmp/ui-reference-test/runtime,
not production media/security paths; its SQLite fixture remains synthetic and isolated.

Consent-bound face references (ADR-030) reuse existing OpenCV/cryptography/SQLAlchemy/React;
no dependency/model/OS permission added. Additive migration 0005_face_references creates a
separate metadata table/indices. Separate lazy face-reference-key; production key/sample absent.
Synthetic HTTP verifier uses isolated PostgreSQL schema/private runtime/tmp storage and stops
its random loopback server at exit. Dashboard build and isolated loopback 5184 browser verification pass; server stopped afterward. Synthetic SQLite/media/key fixtures retained under runtime/tmp/ui-face-reference-test*.

Face quality (ADR-031): existing YuNet/OpenCV/NumPy only; no dependency, model, migration or
OS permission added. One built-in imagegen AI portrait copied to runtime/datasets/face-synthetic.
Original generated artifact remains under /Users/andreapepe/.codex/generated_images/01a11b65-58bc-78f3-9a02-a1767872daae/exec-394cabcc-a55e-4012-a57b-31f27b4e0cf5.png
(default tool output exception); full prompt/hash in project manifest. No real subject image sent
to imagegen. Aggregate replay/diagnostic reports under runtime/exports.

Isolated loopback 5185 browser verification uses actual installed YuNet on the AI image only;
native modes disabled. Server stopped normally; synthetic DB/media/key remain under
runtime/tmp/ui-face-quality-test*. Web build 36 modules / JS 263.88KB, gzip 80.08KB.

Source failure/recovery (ADR-032): existing Python/OpenCV/sounddevice/React only; no package,
model, schema or OS permission added. Installed OpenCV build reports AVFoundation YES.
Native camera access/root cause remains unverified. Real HTTP verification uses generated
pixels and simulated drivers on a random loopback port, with temporary SQLite/runtime root
cleaned afterward. Browser 5186 is isolated under runtime/tmp/ui-source-failure-test*;
native modes disabled. Web build 36 modules / JS 266.03KB, gzip 80.75KB.

Bounded webcam discovery (ADR-033) reuses installed OpenCV; no package, model, OS permission or
persistent device state added. Dashboard offers automatic indices 0–4 discovery or explicit
selection of one index, fixed for the session. OpenCV does not report stable friendly names;
identify the selected index from its preview. Native hardware behavior remains unverified pending
a live webcam acceptance run.

## Italian speech defaults and temporary names (2026-10-09)

No new dependency or model installed. Existing local macOS Alice/Samantha voices generate
synthetic fixtures via say/afconvert; no microphone or audible playback is used. Whisper Tiny
remains the default: a name spike showed Base did not correct the low-confidence Italian
fixture. Italian is now explicit by default in dashboard/API/stream/ASR; English remains an
explicit regression option. New temporary names are display annotations and do not activate
biometric enrollment/recognition or expand retention. Core restarted with workers terminal to
load fixes. Verification: 168 full-suite tests, Ruff/format/mypy, mirror/replay and web build.
Native acceptance CLI is dry-run unless --run plus selected sensors; no OS permissions changed.

The existing 5180 dashboard server was also restarted after confirming idle state, using the
same runtime/tmp/ui-registry-test.db and unchanged local test credential; existing catalog data
was preserved. Both 8000 and 5180 load current speech defaults. Existing browser tabs require
page refresh to load the rebuilt JavaScript (old tabs may still explicitly request English).
