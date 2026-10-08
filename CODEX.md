# CODEX.md — Project Mnemos Autonomous Implementation Guide

## Mission
Implement **Project Mnemos**, a local-first multimodal cognitive assistant whose conversational identity is **Tobi**. Progress autonomously through the operational plan until every realistically executable Task, Epic and Milestone satisfies its Definition of Done and exit criteria. Default posture: **continue working**.

## Source of truth
Canonical Drive folder:
https://drive.google.com/drive/folders/1ePbpeK5whLa_CzFVWJgMKhFgbvC_KK9X

Canonical files:
- 00 Guida Operativa — `1f9pI-MRI9fc8ySRLzKyzxTQmo1n2XjISiNYNL9EQ7lo`
- 01 Visione/Specifica — `1JcTqwcS33izt-XNRlOMk3tYli0BziBgUFm2g3QrpJDE`
- 02 Memoria/Decisioni/Governance — `1N2UokZ7RZDzQrRYBXGZTLj5tX3xC1b9i62foCCNXVGM`
- 03 Piano Operativo — `11qEHyAk8olGoxgKXzt9TMp6AiGKxg8V_8xuef9k_zAQ`
- 05 Architettura/Stack — `1CPNBXIvAKoTXic5AdSY-qS4917wwHaUz_UC61pigvbk`

Authority: current explicit user instruction > accepted ADR > canonical Drive docs > operational plan > local mirror > implementation notes > current code.

## Mirror
`docs/source-of-truth/` is a versioned cache, not authority. Implement:
- `docs:pull`
- `docs:status`
- `docs:verify`
- `docs:push` only with explicit human intent

Default direction: Drive -> local. Detect remote/local conflicts before push.

## Work loop
Choose P0, unblocked, earliest-milestone tasks first, prioritizing the first vertical slice and benchmarks that unblock decisions.

For every task:
1. read requirements/dependencies/ADRs;
2. implement the smallest robust solution;
3. add/update tests;
4. run lint/typecheck/tests;
5. run applicable benchmark;
6. verify failure paths;
7. update technical docs;
8. update installation/data registries if applicable;
9. create/supersede ADR for consequential decisions;
10. mark Done only with objective evidence.

Epic Done = all applicable tasks Done + integrated behavior verified.
Milestone Done = end-to-end exit criteria pass.

Do not stop after a task. Continue while unblocked work exists.
For reversible uncertainty: compare options, benchmark, ADR, choose, continue.
Stop only for unavailable credentials/hardware/data, irreversible/destructive decisions outside policy, privacy/legal approval boundaries, or irreconcilable canonical contradictions. Finish all other unblocked work first.

## Official hardware
- MacBook M1
- 8 GB unified RAM
- macOS
- single-user
- one brain computer
- one active phone sensor

Design provider contracts so heavy workloads can later move to a personal server.

## Architecture
Initial architecture: **modular monolith**.
No microservices/Redis/Kafka/NATS/distributed scheduler without measured need.

Processes:
- Python `mnemos-core`: FastAPI, orchestration, world state, memory, decisions, actions
- React/Vite `mnemos-web`
- PostgreSQL + pgvector in Docker Compose
- optional isolated ML workers only after benchmark evidence

Use bounded async queues and backpressure.

Core toolchain: Python 3.11, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2, Alembic, asyncio, uv.
Web: TypeScript, React, Vite, pnpm.

## Data containment
Keep generated state under:
```
runtime/
  data/postgres/
  media/{audio,video,keyframes,evidence}/
  models/
  cache/{huggingface,torch,onnx,ocr}/
  logs/
  tmp/
  datasets/
  exports/
```
Redirect external ML caches there where possible. Register unavoidable system-level installs.

Docker is for reproducible infrastructure. Run ML/media natively on macOS when Metal/MPS/device access benefits. Goal is containment + reproducibility, not “everything in Docker”.

## Phone satellite
MVP uses a mobile browser, not native app:
1. Mac creates short-lived pairing session and QR.
2. Phone opens trusted HTTPS LAN page.
3. User grants camera/mic.
4. WebRTC streams A/V to Mac.
5. Core normalizes it like local camera/mic.
6. Tobi can return text/status/TTS.

Phone UI: front/back switch, preview, start/pause/stop, connection/media status, telemetry, TTS, optional torch/zoom.

Use WebRTC; FastAPI WebSocket for signaling; prefer aiortc behind a MediaTransport interface. Initial transport 720p up to 30 FPS, adaptive bitrate, low-latency-first. Internet/TURN is not first-MVP scope.

## Rolling buffer
Up to 5 minutes audio and resource-bounded video. Circular and non-persistent. Persist only by explicit recording/meeting/evidence/user request/event policy.

## Perception
All models are provider-backed.

Detection: permissively licensed M1/ONNX/CoreML-friendly baseline; benchmark YOLOX/RT-DETR family or equivalent. Ultralytics only as experimental/licensing-tracked adapter.
Tracking: ByteTrack/equivalent, avoid re-identification every frame after confident binding.
OCR: Italian + English, ROI/event-driven.
Faces: persistent identity only for enrolled/authorized people; prefer permissive YuNet + OpenCV SFace or benchmarked equivalent; unknowns remain anonymous session tracks.
Object physical identity = semantic retrieval + local features + OCR/marks + tracking continuity + context/evidence fusion.

## Audio
Italian + English.
Pipeline: source -> rolling buffer -> VAD -> local ASR -> partial/final transcript -> diarization -> speaker identity -> conversation -> intent/event extraction.
Use whisper.cpp or equivalent Apple-Silicon-friendly local ASR baseline.
Primary user's voice supports enrollment and command authorization.
Diarization can refine asynchronously.

TTS provider: local macOS/browser in MVP; future ElevenLabs adapter possible.

## Embeddings/search
EmbeddingGemma 2 is primary MultimodalEmbeddingProvider candidate for text/OCR/images/keyframes/object crops/audio/cross-modal retrieval/local zero-shot routing.
Benchmark 256/512/768 dimensions on M1/8GB. Measure accuracy, latency, RAM, load cost, index size. Lazy load and evict under pressure.
Do not treat semantic similarity alone as physical instance identity.

DB: PostgreSQL + pgvector. Model graph relations relationally first; no Neo4j without real evidence.
Media: local filesystem behind MediaStore; future S3-compatible backend.
Search combines SQL + pgvector + full-text + temporal + relations + provenance. Expose **Ask Tobi**.

## Decision hierarchy
Level 0: deterministic rules/thresholds/state machines.
Level 1A: local semantic routing; optional EmbeddingGemma zero-shot after benchmark.
Level 1B: OpenAI Decisions API with `gpt-6-luna` for bounded predicate/choice/score decisions.
Level 2: OpenAI Responses API via provider abstraction for extraction, ambiguity, summary, planning, explanation/reasoning.

Models propose. Policy authorizes. Tools execute. No privileged action bypasses Policy Engine.

Cloud defaults:
- biometrics stay local;
- continuous raw A/V stays local;
- transcript/event state may go cloud when needed;
- selected frame/crop may go to configured vision fallback;
- all cloud calls observable/tagged.

## Memory/conversations
Memory types: semantic, episodic, prospective.
Hot memory bounded and in-process. Long-term memory preserves provenance/confidence.
Conversation records can include participants, time, utterances, optional source audio/timecodes, topics, summary, decisions, tasks, commitments and linked entities. Outside explicit recording mode, do not persist entire conversations by default.

Tobi does not require a wake word. Use speaker identity + direct address + semantics + context + recent interaction state. Saying “Tobi” strongly raises confidence. Third-party speech cannot gain command authority merely by being audible.

## Actions
Separate ActionProposal, ActionPolicyDecision, ActionExecution.
Risk: automatic / audit / confirmation / strong-confirmation / prohibited.
MVP real actions: local memory, local task, local reminder, notification.
External production integrations follow after memory/reasoning/policy stability.

## Dashboard
Build a real dashboard: live feed/overlays, transcript, source/WebRTC state, event timeline, entities/details/last-seen, conversations, memories, tasks/reminders, Ask Tobi, runtime/model status, storage/cloud telemetry, settings/privacy, evidence/debug.

## Licensing/security/testing
Track code + weight license, commercial constraints, version/hash, replacement path. Never silently introduce non-commercial weights to product paths.

Mandatory tests: unit, contract, integration, replay perception, benchmarks, E2E phone->Mac, reconnect/failure, privacy/retention, regression. Commit reproducible test media where safe.

M1/8GB discipline: bounded queues, frame sampling, low-res inference, lazy loading/eviction, avoid duplicated heavy runtimes, memory pressure telemetry. Feature is not complete if it thrashes memory without degraded mode.

Observability: FPS, drops, queues, inference/ASR/identity/search/decision latency, cloud calls/cost, memory pressure, model load/unload, storage growth, WebRTC RTT/jitter/loss, interrupt usefulness, false-identity rate.

Data safety: no persistent arbitrary passerby IDs, no unknown naming without enrollment, no recording-policy bypass, no biometrics cloud-by-default, no whole-day raw cloud streams, no destructive actions without policy, no silent retention expansion.

## First product-working vertical slice
1. core starts on Mac;
2. dashboard;
3. QR pairing;
4. phone browser trusted HTTPS LAN;
5. camera/mic permission;
6. WebRTC A/V;
7. live feed + transcript;
8. generic detection/tracking;
9. face detection;
10. OCR;
11. “Tobi, memorizza questo come il mio zaino”;
12. enrollment;
13. object disappears;
14. object reappears;
15. specific entity label + confidence + evidence + last-seen;
16. authorized-person enrollment;
17. contextual reminder;
18. grounded memory query to Tobi.

The product is not “working” because API/UI/tables exist. It is working when this slice passes repeatably live and with replay fixtures.

## Final loop
Repeat source sync -> choose next task -> implement -> test -> benchmark -> fix -> docs/ADR/registries -> mark Done with evidence -> reevaluate Epic -> reevaluate Milestone -> continue.

If blocked, create/update `BLOCKERS.md` with blocker, affected tasks, attempts, exact human action required, and all other completed work. Do not use “needs clarification” as a substitute for reasonable engineering judgment.

## Sol/Luna agent operating policy

For implementation work, **Sol acts only as the orchestrator**: reads current status, breaks down tasks, freezes shared contracts, delegates, arbitrates and evaluates acceptance. **Only GPT-6 Luna subagents** implement code, investigate, review, test and integrate. This is a mandatory project execution policy; read `docs/runbooks/SOL_LUNA_ORCHESTRATION.md`.

Use project-local `.codex/config.toml` and `.codex/agents/*.toml` for Luna-only child defaults and typed custom roles. Check the effective settings in your Codex runtime before the first wave. If these files are not loaded, do not silently spawn Sol subagents.

Because implementation may already exist outside GitHub's `main`, first perform a read-only reconciliation of the actual local/current branch and uncommitted work. Never reset, overwrite or recreate features purely because source snapshots have old statuses.

Parallelize only independent tasks with exclusive file ownership and ideally separate worktrees. Review must be independent of implementation. A Luna integrator runs aggregate tests and prepares merges; Sol accepts the result only after evidence and canonical exit criteria. Heavy ML/database tasks run serially on M1/8GB.
