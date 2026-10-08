# Registry mutation verification — 2026-10-08

T017 is In Progress. Manual non-person create/update run PolicyEngine and commit a linked
execution audit atomically. Authenticated generic HTTP cannot enroll a person with a claimed
consent flag, inject evidence/model references, change entity kind/owner/retention or bypass
policy. Names/attributes are not duplicated in audit payloads. Raw repository.save remains a
low-level infrastructure primitive for migrations/tests; user execution must use GovernedRegistry.

Acceptance evidence:
- Unit/integration: protected field rejection, server-owned actor/provenance, denial → no write,
  audit failure → rollback of both create and update, PostgreSQL isolated schema create/update.
- HTTP: unauthorized requests rejected, consent/reference spoofing rejected, CRUD reload.
- Full `scripts/check` with MNEMOS_TEST_MODELS, MNEMOS_TEST_SPEECH and real local PostgreSQL:
  76 passing tests, no skips; Ruff, strict mypy, eight mirror hashes and contract replay pass.
- `python -m mnemos.registry_benchmark`: isolated disposable SQLite, 100 synthetic entities,
  300 policy execution audits; p95 create 1.36ms / update 1.18ms / delete 2.34ms on arm64 M1.
  Output runtime/exports/registry-benchmark.json. No installation entities in benchmark.

Remaining: voice review grounded in actual server transcripts/evidence, reference/biometric revocation,
authorized-person enrollment, physical-reference capture and integrated canonical acceptance.
No biometric samples or real-person recordings were acquired.


Governed delete verified: strict confirmation plus exact current name, computed strong policy,
wrong-name/missing/string confirmation rejection, not-found on retry, no deletion for people,
referenced entities or inbound relations; failed audit rolls the deletion back. Actual isolated
PostgreSQL create/update/delete passes. The production core loopback create/update/reload test
produced two authorized audits in 160ms total; synthetic fixture/audits were cleaned afterward.
Report: runtime/exports/registry-http.json.

Production web bundle builds successfully. Browser at isolated port 5180/database/token observed
create and rename success, wrong name + checked confirmation keeping Delete disabled, exact
current name + checked confirmation enabling Delete, then Disconnect clearing catalog/token.
Final delete was verified through API tests, not triggered in browser. Screenshot contains only
synthetic state: runtime/exports/registry-dashboard.jpg. Temporary server shut down normally.

Later T017 acceptance: manual/voice-reviewed person/object registry flows, consent/revocation
and concurrent-stop verification are now complete. ADR-028 corrects previous attribution of
downstream physical acquisition/matching to T017; see registry-acceptance.md. The separately
requested automatic person approval remains open. No full entity-memory milestone is Done.
