# External blockers — 2026-10-08

No blocker currently prevents continued local implementation. Do not stop the autonomous loop.

Scoped pending input: the later automatic-person-approval request has an unanswered scope
question (existing consented identities versus new non-biometric contacts). Recorded in
docs/plan/automatic-person-approval.md. No automated biometric consent/identity/authority
was inferred. This is not a blocker for T018 object quality or other independent work.

Known external verification requirements (not yet global blockers):
- M7/T058–T062: selected wearable hardware/SDK and physical device access are not provided.
  Continue Mac/phone implementation first; later record exact model and SDK access required.
- Live phone HTTPS trust and camera/mic permission need the physical phone and OS/browser grants.
  Implement transport/replay/reconnect tests first. Never report live phone E2E as passed without it.
- T075 field pilot and consented biometric evaluation need authorized participants and real trials.
  Prepare privacy/security and safe fixtures; do not enroll real people automatically.
- Cloud integrations need configured provider credentials at runtime. Use contract tests until available;
  do not infer product credentials from connected Codex apps.

Resolved: Docker was installed but stopped; launched existing Docker and provisioned the project
PostgreSQL/pgvector service. Network-restricted dependency installs succeeded with approved scope
and repository-contained caches. No requirement or action policy was relaxed.

Remaining verification boundary: T090 native Docs/Sheets OAuth transport is implemented and
simulated-response tested, but standalone MNEMOS_DRIVE_OAUTH_TOKEN is not configured. Canonical
write roundtrip needs an explicit human docs:push instruction and an authorized OAuth credential;
CODEX.md forbids inferring this from the implementation goal. Connected Drive reads already
verified canonical MIME types and timestamps. Continue other work; no credential request blocks
local implementation. T007/T013 native-source and representative T009/T012 quality checks remain
unverified; owner-controlled replay preview and stop are verified without OS sensor grants.

2026-10-09 native verification update (T007/T013, not global blocker): an earlier
owner-selected camera/microphone attempt ended with video source/normalization failure
before any video frame. Root cause was not retained and cannot be inferred as permission
denial. OpenCV has AVFoundation support. ADR-032 now provides fixed stage codes, cleanup
status and explicit recovery; simulated driver/HTTP/browser checks pass. Human action
for native acceptance: select permitted sensors in the installation dashboard, grant OS
access if prompted, retry and observe frames/audio with the new diagnostics. No native
permission bypass or automatic reopening was introduced; independent work continues.

### 2026-10-09 — Live speech error subtype unavailable

Owner's native capture reached 3988 normalized audio chunks and 310 processed frames before
`local speech processing unavailable`; the old worker retained no exception code. Exact root
cause cannot be reconstructed from discarded private buffers. ADR-035 sets the agreed Italian
default and fixes the independently reproducible unsupported-auto-language shutdown, adding
sanitized speech error codes. 168 real-model/DB suite tests and actual-core Italian replay pass.
No claim that the original live failure is fixed: owner's next live retry can provide a bounded
error code if it recurs. T013 remains In Progress. Temporary automatic/display names are now
implemented (ADR-034); persistent automatic enrollment/identity scope remains open separately.
