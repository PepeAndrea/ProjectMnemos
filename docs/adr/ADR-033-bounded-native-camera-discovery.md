# ADR-033 — Bounded native camera discovery

Accepted 2026-10-09. Native camera acquisition is available in two modes after the owner
explicitly consents and starts a native capture: automatic probing of indices 0 through 4, or
an explicit owner-selected index in that range. Automatic mode considers a camera usable only
if OpenCV opens it and its first read returns a frame; failed candidates are released before
the next probe. Manual mode opens only the selected index. The selected device is held for the
session; Tobi never switches devices or reopens a camera after capture starts. If the selected
camera is unavailable, the existing sanitized `camera-open-failed` state and explicit recovery
flow apply.

This handles macOS camera enumeration where Continuity Camera may occupy the first index or an
opened virtual device may provide no frames while a local webcam exists at a later index. The
probe is deliberately bounded to five indices to avoid an unbounded hardware scan. OpenCV offers
no portable camera-enumeration contract or stable friendly device names for this installed
backend. The dashboard therefore labels manual choices by index and retains automatic mode;
the owner can identify a camera from the live preview.

No additional permission, persistence, dependency, or data layout is introduced. Every candidate
is accessed only under the existing per-session camera consent. Unit tests simulate unavailable,
opened-but-frame-less, and working indices and verify release. These tests do not prove native
macOS camera access; T007 remains in progress pending an explicit live webcam verification.
