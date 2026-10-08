# ADR-022 — Governed manual entity mutations

Status: accepted, 2026-10-08. Scope: T017 partial implementation.

The authenticated entity API previously wrote straight to the repository. Authentication alone
was insufficient to satisfy the architecture's proposal → policy → execution requirement;
a validated biometric consent boolean also did not prove actual enrollment consent.

Manual create/update now construct server-owned entity_create/entity_update proposals (audit
risk), evaluate PolicyEngine and atomically commit the entity mutation and linked
ActionExecution in local_action_audit. Owner identity comes from server authentication, never
client speaker scores. The audit stores action/actor/entity IDs and policy, without duplicating
entity names, attributes, references or biometric data. Failures roll back both writes.
The LocalActionRow model is shared from storage; the existing 0002 table needs no migration.

Generic create/update reject all people pending a dedicated verified consent/enrollment flow.
Creating arbitrary evidence/embedding references is rejected. Updates preserve relation IDs, entity kind,
existing reference IDs, retention and owner. Manual provenance is server-generated human
owner-dashboard provenance. Legacy ownerless non-person records can be claimed only by the
single authenticated installation owner; records belonging to another owner are rejected.

Alternatives: bearer authentication alone leaves a policy bypass; separate audit commits can
leave an unaudited mutation or false success after transaction failure. One SQL transaction
matches the existing scheduler design without another service or dependency.

Evidence: tests/test_registry.py exercises protected fields, consent/reference spoofing,
policy denial, atomic create/update rollback and real isolated PostgreSQL persistence.
tests/test_api.py checks the HTTP boundary. The integrated suite has 76 passing tests with
all opt-ins, none skipped. Synthetic SQLite benchmark on M1: 100 creates + 100 updates + 100 deletes,
300 linked audits; create p95 1.36ms, update p95 1.18ms, delete p95 2.34ms. This measures local overhead,
not PostgreSQL throughput or biometric enrollment quality.

Remaining T017: reference/biometric revocation, review of server-owned final voice proposals,
actual authorized-person consent and enrollment, integrated acceptance. This ADR does not
assert T017, an epic or the first working vertical slice complete.


Deletion addendum: owner POST /entities/{id}/delete requires strict confirm_irreversible=true
and the exact current stored name. Policy computes strong-confirmation risk. It deletes only
non-person entities without reference/embedding IDs or inbound relations; reference/biometric
revocation is a separate future flow. Generic CRUD cannot introduce/change relation IDs while
this boundary is incomplete. Delete and its ID-only execution audit commit atomically; failed
audit leaves the entity intact. Repeating deletion returns not-found. No production user record
was deleted for verification. Tests use synthetic isolated SQLite/PostgreSQL fixtures.
