# ADR-024 — Consent-bound local biometric vector storage

Accepted 2026-10-08. T017 partial implementation; complements ADR-022/023.

A dedicated authenticated owner path records an explicit attestation of subject permission,
separate face/voice scopes and an aware future expiry. This assurance is deliberately named
`owner-attested-subject-permission`: it does not independently verify the subject's consent,
identity, legal basis or biometric sample quality. Generic entity writes still reject people.
Recognizing someone grants neither command authority nor permission to record conversations.

Decision: keep consent metadata and encrypted vectors in separate tables in the existing
PostgreSQL transaction boundary. A separate database/service would complicate atomic revocation
without measured isolation benefits on this single-owner M1. Vector storage is server-internal;
there is no HTTP upload/read endpoint for raw templates. Future provider/acquisition interfaces
must preserve these checks rather than allowing client identity/authority claims.

Use PyCA cryptography 50.0.2 AESGCM, a random 32-byte key and fresh random 12-byte nonce per
vector. Authenticated metadata binds envelope version, template/consent IDs, modality, provider
and dimensions. Finite nonzero vectors are normalized and packed float32, at most 4096 values;
at most 20 templates per modality/consent. The official API documents authenticated encryption,
nonce requirements and authentication failures:
https://cryptography.io/en/latest/hazmat/primitives/aead/ .

The local key is separate from the DB at runtime/data/security/biometric-key, lazily created
only on first authorized template storage, regular current-owner file mode 0600, parent 0700,
no final symlink following. No production key or real template was created by these checks.
Existing ciphertext plus a missing key refuses regeneration. Missing/insecure/invalid keys,
invalid envelopes, altered authenticated metadata, expiry or revoked scope deny access.
Keychain/hardware isolation, rotation, backup lifecycle and plaintext memory erasure remain
future security work; the local file is not a claim of protection from a compromised OS owner.

Reads commit ID-only policy/execution audit before returning plaintext. Explicit revocation
requires authenticated owner, exact current name and strong confirmation. Consent expiry was
pre-authorized at grant; a bounded worker locks up to 100 active expired records per batch.
Entity, templates, state change and audit commit together; audit failure rolls everything back.
Read authorization checks expiry even before cleanup succeeds. Expired/revoked consent metadata
retains IDs, scopes, attestation version/dates for audit, not the deleted person's name/vector.
This removes active DB rows, not forensic copies in WAL, OS caches or future backups. Recognition
providers must evict any in-memory gallery on revocation before they are enabled.

Evidence: 98 tests pass with installed vision/speech models and isolated PostgreSQL fixtures;
no skips. Failure paths include metadata tampering, lost/insecure key, scope denial, missing
confirmation, audit rollback, stale-name revoke, expiry access denial and 101-record cleanup
without starvation. Synthetic isolated SQLite benchmark (50 x 128-dimensional vectors): p95
grant 1.14ms, encrypted store+audit 1.70ms, read+audit 1.34ms, revoke+audit 1.91ms. These timings
compare overhead to a separate service's added lifecycle; they do not measure recognition accuracy.
Real loopback HTTP/PostgreSQL consent → rename → stale-name denial → revoke passed in 154ms,
three linked executions, no names in audit, fixture removed. See person-enrollment verification.

T017 remains In Progress: actual authorized sample acquisition, physical object references,
quality/accuracy calibration and integrated canonical acceptance are not yet verified.

Expiry presentation also fails closed: the dedicated list queries only active, future-deadline
consents. Status computes effective expiry and exposes cleanup_pending separately from stored
metadata. Forced purge-audit failure proves rolled-back rows never reappear as authorized people.
