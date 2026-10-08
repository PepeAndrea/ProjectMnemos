# ADR-032 — Source failures and explicit worker recovery

Accepted 2026-10-09. Supports partial T007/T013; native acceptance still pending.

Use finite stage-specific MediaSourceFailure codes (OSError compatible) at video/microphone
boundaries. Separate camera opening/reading, replay opening/reading/format and driver release
failures. Public state contains code, a fixed message, worker_active and source_cleanup_failed;
never driver exception text, device names, file paths, frames or transcripts in diagnostics.
Keep the first source/model failure when secondary worker cleanup also fails. Release detaches
the handle before calling the driver and records release failure without retaining that handle.
This does not prove the OS released a device whose driver raised an error.

Configuration and read failures now run through source cleanup. Invalid/nonfinite reported
video FPS falls back to configured FPS; empty replay is an error while EOF after valid frames
is normal. Unsupported, unbounded or non-uint8/non-BGR frames are rejected before serialization.
An error arriving after explicit Stop does not turn a deliberate stop into a new source failure.

The dashboard keeps Stop enabled while a failed session still has a live worker. New starts
remain disabled until worker completion; the API independently returns 409 for a live prior
session. Unknown connection state blocks starts but permits Stop. Poll errors are separate
from operation errors and clear after a successful poll. Recovery always requires a new explicit
start, retains sensor consent gates and never auto-reopens hardware.

Alternative considered: parsing platform exception strings. Stage codes give stable behavior
without platform-specific/private text. No new package, process, schema or OS permission is
needed. Real HTTP/SQLite fixture verifies auth, failed-worker exclusion, terminal cleanup,
new-session preview and Stop. Simulated cleanup after gate release: 92.64ms. Fifty warm simulated
open failures: p50 104.64ms, p95 110.28ms. These are worker timings, not native device recovery.

Local OpenCV build reports AVFoundation YES. A previously observed real camera attempt failed
before any video frame with a generic source error; its root cause was not recorded. Neither
the build flag nor simulated recovery proves working camera/microphone or macOS permission.
Native T007/T013 and milestone exits remain unverified. See source-failures.md verification.
