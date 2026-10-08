# Person consent and encrypted storage verification — 2026-10-08

T017 remains In Progress. Dedicated owner-authenticated consent registration, rename, status,
strong-confirmed revoke and automatic expiry are implemented. Attestation is not independent
verification of subject permission. No person image, voice or identity accuracy was acquired.

Checks: 98 tests pass with MNEMOS_TEST_MODELS=1, MNEMOS_TEST_SPEECH=1 and isolated PostgreSQL
schemas; Ruff/format/strict mypy, eight mirror hashes and replay pass. tests/test_biometrics.py
covers encrypted vector storage/read with synthetic numeric values, scope and confirmation,
metadata authentication, lost/insecure key, atomic audit rollback, expiry denial and bounded
101-record expiry cleanup. tests/test_api.py covers strict booleans, naive/invalid expiry,
owner authentication, metadata no-store, forbidden generic person writes and stale-name revoke.

`python -m mnemos.biometric_benchmark`: isolated temporary SQLite, 50 synthetic 128-dimensional
vectors, all revoked; p95 grant 1.14ms, encrypted store+audit 1.70ms, read+audit 1.34ms,
revoke+audit 1.91ms. runtime/exports/biometric-benchmark.json. No identity accuracy claim.

`python -m mnemos.person_enrollment_verify`: fixed loopback development core/PostgreSQL,
uniquely named synthetic metadata, no sensors or vectors. Consent → scope/status/list → rename
→ stale-name revoke rejection → revoke passed in 154ms. Three linked execution audits contained
no personal name; active entity absent, revoked consent readable. Cleanup removes only this
run's synthetic entity/consent/audits. runtime/exports/person-enrollment-http.json.

Production web build passes (32 modules). Browser on isolated port 5180 verified initial
unchecked scopes/attestation and disabled submit, explicit synthetic face-only consent,
expiry retention (datetime input fix), persisted scope/deadline metadata, wrong-name revocation
remaining disabled, and Disconnect clearing token/catalog/person state. Request abort and auth
generation prevent stale asynchronous results repopulating disconnected state. No final browser
revocation was submitted. Screenshot runtime/exports/person-consent-dashboard.jpg.

During verification an additional manually entered `andrea` record appeared in this isolated
SQLite database. It was preserved; no subject consent or real biometric acquisition is inferred.
Screenshot therefore includes manual metadata as well as synthetic verification, not exclusively
synthetic content. The isolated DB/server is retained for continuity and is not installation state.
Capture showed a source failure in that environment; this is not evidence of working live sensors.

Remaining acceptance: authorized sample acquisition, provider quality checks and physical
references; complete first vertical slice, live devices and representative accuracy. ADR-024
records encryption, key recovery and deletion limits; no task/epic/milestone promoted to Done.

Additional expiry regression: forced audit failure during automatic purge leaves DB rows intact,
but the dedicated owner list immediately excludes expired subjects and consent status reports
expired + cleanup_pending. A subsequent successful purge clears cleanup_pending. This verifies
that delayed deletion cannot misrepresent expired consent as active, independently of the worker.

After the expiry correction the full 98-test suite passed again (no skips), and the restarted
real core repeated the HTTP/PostgreSQL flow in 108ms. The isolated UI server was restarted with
the updated code, preserving its database/manual additions; no enrollment data was migrated.
