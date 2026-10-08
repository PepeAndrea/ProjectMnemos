# Reviewed voice person enrollment — 2026-10-08

Implemented logical person registration from an owner-reviewed server-owned final ASR
proposal. The owner corrects the name and selects separate face/voice consent, attests
the subject's permission and supplies an aware future expiry. This does not acquire
biometric samples, identify the speaker or authorize commands/conversation recording.

The server assigns the stable proposal entity UUID. Person, consent and ID-only review
audit commit together. Authentication, explicit confirmation, strict booleans and scope
validation fail closed; SQL failure restores the pending proposal without partial rows.
Existing entity IDs cannot be converted or duplicated. Extra speaker-authority fields
and naive deadlines reject. Stop clears proposals and transcript state.

`tests/test_voice_person_enrollment.py` covers these boundaries. Full `scripts/check`
with model, speech and PostgreSQL opt-ins: 113 passed, no skips; Ruff, formatting,
strict mypy (50 source files), eight mirror hashes and contract replay passed.

Actual local Whisper → HTTP → PostgreSQL via `python -m mnemos.voice_person_verify`:
proposal 3441.06ms, owner-reviewed synthetic person transaction 40.74ms; anonymous
proposal denied, one linked consent audit, face-only scope, stop cleared private state,
explicit revocation succeeded. This run's unique synthetic person/consent/audit rows
were removed. Aggregate report: runtime/exports/voice-person-http.json. No native
sensors, real subject, biometric samples or cloud call. These are observed integration
timings, not representative ASR/name/identity accuracy.

Frontend person selection, editable suggested name and separate consent/deadline fields
passed isolated browser verification on port 5182. All consent inputs initially empty
and unchecked; submit remained disabled until the separate catalog confirmation. The
corrected synthetic name persisted with face-only consent after Stop and authenticated
reload. Stop cleared transcripts; reload and Disconnect removed token and private people
state. The temporary server was stopped normally. Synthetic proof screenshot:
runtime/exports/voice-person-dashboard.jpg. SQLite fixture remains isolated under
runtime/tmp/ui-voice-person-test.db; no production keys/samples acquired.

Additional concurrent-transaction test verifies duplicate claim rejection and immediate
Stop while a confirmed person grant is blocked, followed by successful commit without
restoring private state. Applicable 50-vector benchmark p95 grant 1.706ms, store/audit
2.527ms, read/audit 1.552ms, revoke/purge/audit 1.934ms. See ADR-027.
T017 stays In Progress.
The subsequent request for automatic approval is not yet implemented: clarification is
pending on existing consented people versus new non-biometric contacts. Neither an audio
name nor owner automation authorization attests another subject's biometric permission.
