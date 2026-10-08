# ADR-025 — Explicit owner association to a visible object track

Accepted 2026-10-08. T017 incremental implementation, not completion of dependent T018–T022.

The catalog/voice-review path previously persisted a name without selecting anything in the
video. An owner can now choose a numbered current detector track and an already enrolled
owner object, then explicitly confirm that association. The server checks the active capture,
current track, freshness within two seconds, modality boundary and owner object before audit.
Client boxes/classes, guessed persistent identity or speaker authority are never accepted.
Person/face tracks and person entities cannot use this non-biometric route.

Decision: use an explicit bounded session association before cross-session reidentification.
Its evidence is the owner's current selection plus tracker continuity, not similarity or model
identity accuracy. Detection confidence remains separately labelled detector confidence.
Bindings are volatile and limited by the existing 128-track capacity. Any missed frame removes
the binding and pending claim; a new selection is needed even if the IoU tracker retains its ID.
This conservative continuity rule avoids transferring a human name through a lost/ambiguous
association. Reference capture and evidence fusion remain required for recognition on reappearance.

The PolicyEngine classifies track_bind as confirmation, ignoring caller/model risk. An ID-only
execution audit links capture, track and catalog entity; no raw pixels/audio, name, box or durable
anonymous person ID is stored. There is no schema migration or additional provider. A successful
audit authorizes the selected session association; it is not proof that the track was still visible
when the response arrived. The response therefore includes bound=false if stop/loss intervened.

DB I/O runs outside the capture lock so Stop clears volatile state promptly. Each claim has its
own opaque token: an old completion cannot consume/rebind a newer claim after disappearance.
DB failure releases only that claim for retry; duplicate/in-flight selections reject. UI request
abort guards prevent late control/review/binding responses repopulating disconnected state.
The display resolves IDs through the current catalog; catalog refresh removes obsolete names.

Measured 100 synthetic associations: claim/finish p95 0.0084ms, isolated SQLite policy+audit
p95 0.832ms. No extra ML loading or media copies. The benchmark measures coordination overhead,
not representative detector/tracker/identity accuracy. tests/test_track_binding.py verifies scope,
freshness, consent, audit rollback, stale completion and stop; real PostgreSQL uses an isolated
schema. Browser uses synthetic pixels/detections and separate DB on loopback 5181, not sensors.

Remaining: actual authorized person samples, physical reference acquisition/quality, calibrated
matching and integrated acceptance. Human session association does not satisfy those criteria;
T017 stays In Progress and no epic/milestone is complete.
