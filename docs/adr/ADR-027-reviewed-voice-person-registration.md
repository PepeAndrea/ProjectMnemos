# ADR-027 — Reviewed voice person registration with separate consent

Accepted 2026-10-08. Extends ADR-023/024 to logical person enrollment from a
server-owned final transcript; does not enable automatic biometric approval.

The same temporary ASR inbox now supports owner selection of object or authorized
person. The owner can correct the proposed name. Person registration requires
separate face/voice choices, subject-permission attestation, future aware expiry and
explicit confirmation. These fields start empty/unchecked in the dashboard. ASR text,
confidence and a spoken name cannot attest permission, identify a speaker or confer
command authority. Actual biometric acquisition remains a separate provider path.

Use the existing PersonEnrollment transaction and policy path. The server supplies the
stable entity UUID derived from capture/utterance and the reviewed proposal UUID;
clients cannot supply speaker claims, arbitrary identity IDs or transcript provenance.
Entity, consent and ID-only audit commit together. Existing IDs reject rather than
converting a catalog object or replacing another person. Failure releases the claim
for retry; consumed proposals cannot create another entity.

Do not hold the capture lock across storage. An explicitly confirmed transaction may
finish after Stop, while Stop immediately clears temporary speech and proposals.
Its late completion never restores that private session state. Concurrent claims
reject. This is the same durable-mutation/volatile-capture separation as ADR-023.

Evidence: real local Whisper/HTTP/PostgreSQL synthetic corrected person roundtrip
produced the proposal in 3441.06ms and committed review in 40.74ms. Consent scope,
linked audit, stop clearing, revocation and fixture cleanup verified. Isolated browser
test verified defaults, corrected name, face-only consent, persistence after reload,
and private-state clearing on disconnect. Unit failure tests cover unauthorized and
malformed requests, atomic audit rollback, duplicate IDs and concurrent Stop.

Rechecked 50 synthetic vectors in isolated SQLite: p95 consent grant 1.706ms,
encrypted store/audit 2.527ms, read/audit 1.552ms, revoke/purge/audit 1.934ms. Reusing
the existing transaction meets current local overhead needs without another service.
No sample or identity quality conclusion follows from these measurements.

The subsequent owner request for automatic approval is recorded separately; its scope
is pending clarification between already consented identities and non-biometric
contacts. No automatic consent or name-to-speaker identity inference was activated.
Manual authorization remains operational while that choice is pending.
