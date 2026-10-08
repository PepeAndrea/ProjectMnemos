# Project Mnemos

Project Mnemos is a local-first multimodal cognitive assistant. Its conversational interface is **Tobi**.

## Start here

1. Read `AGENTS.md`.
2. Read `CODEX.md`.
3. Verify `docs/source-of-truth/manifest.json`.
4. Treat the canonical Google Drive folder as the authoritative product source:
   https://drive.google.com/drive/folders/1ePbpeK5whLa_CzFVWJgMKhFgbvC_KK9X

The repository is authoritative for executable code, tests, migrations and implementation state. Google Drive is authoritative for approved requirements, governance, architecture and the operational plan.

Current verified implementation includes the authenticated core, PostgreSQL registry, local
replay/video/PCM providers, bounded capture and dashboard preview, ONNX detection/face/tracking,
a durable temporal reminder inbox, policy contracts and canonical mirror sync. Start and verify
using [the development runbook](docs/runbooks/development.md). Objective task evidence lives in
[docs/plan/progress.json](docs/plan/progress.json).

The full product vertical slice is still in progress: phone HTTPS/WebRTC, speech/OCR, enrolled
physical identity, grounded memory queries and contextual reminders have remaining work. Native
sensor verification and canonical OAuth publishing are not inferred from replay tests.
