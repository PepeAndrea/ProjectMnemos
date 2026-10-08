# T017 registry acceptance audit — 2026-10-08

Canonical task: Entity CRUD e enrollment, manual/voice creation of authorized people
and objects, dependency T001 (Done). Allocation rationale: ADR-028. The downstream
quality/biometric/recognition tasks remain open and prevent M2 completion.

| Requirement | Inspected evidence |
| --- | --- |
| Manual object CRUD | GovernedRegistry; tests/test_registry.py; tests/test_api.py; actual PostgreSQL registry-http report; synthetic browser create/rename/reload |
| Manual authorized person enrollment/read/rename/revoke | PersonEnrollment; test_person_consent_separate_scopes_auth_retention_and_revocation; actual person-enrollment HTTP report; dedicated browser panel |
| Voice object creation | Server final ASR inbox + authenticated correction; actual Whisper/HTTP/PostgreSQL voice-enrollment report; browser review and persistence |
| Voice authorized person creation | approve-person route + stable server ID + separate consent; actual Whisper/HTTP/PostgreSQL voice-person report; synthetic browser corrected person persisted after reload |
| Permission/retention boundaries | Strict scopes/attestation/expiry, owner-only endpoints, generic-person bypass rejection, immediate expiry denial/revocation and separate native-sensor consent tests |
| Policy/audit/failures | Atomic entity/consent/action audit; SQL rollback; duplicate/stale proposal and protected-ID rejection; concurrent Stop while grant blocked; no late private-state restoration |
| Reproducibility/docs | Locked environments, migrations 0001–0004, scripts/check, registries, development/person/object runbooks, ADR-022–028 |

Latest full verification: 113 tests pass with local vision/speech models and actual
PostgreSQL opt-ins, no skips; Ruff/format/strict mypy, eight mirror hashes and replay
pass. Registry benchmark rechecked: 100 objects, 300 atomic audits, isolated SQLite,
p95 create 1.111ms/update 1.037ms/delete 2.113ms. Consent benchmark (50 synthetic
vectors) p95 grant 1.706ms/store 2.527ms/read 1.552ms/revoke 1.934ms. Neither is a
representative identity/ASR accuracy benchmark. Existing actual PostgreSQL tests
exercise transaction/storage compatibility, not production throughput.

T017 baseline registry deliverable is verified. New automatic-approval request remains
open, not enabled; no real subject samples or full physical identity recognition were
acquired/proven. T018, T020, T027, E06/E07 and M2 are not promoted by this audit.
