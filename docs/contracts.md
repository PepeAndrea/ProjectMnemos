# Domain contracts v1

Executable source: apps/core/mnemos/domain.py. Portable schemas: packages/contracts.
Regenerate with `python -m mnemos.export_contracts`; changes require schema review/versioning.

Entity owns name, aliases, attributes, relation/reference IDs, ownership, confidence, provenance
and retention. IdentityEntity references face/voice templates and authorized images in a
separate biometric store; templates never appear in public payloads. Anonymous people are
session scoped. Persistent identification requires explicit enrollment and consent.
Observation describes one perception result including candidates, context, source/track/session,
confidence, evidence and a volatile buffer reference. Event aggregates observation IDs.
Memory is a separate selected semantic/episodic/prospective record, never an automatic dump.
Conversation tracks participants, utterances, topics, summary and extracted decision/task/
commitment references with independent recording and transcript-persistence flags. Utterance
has anonymous/session speaker ID, optional enrolled identity, source timecodes, IT/EN text,
partial/final status and confidence. Partial text cannot reference durable audio.
Task and Reminder have explicit lifecycle states and provenance. Trigger conditions combine
with AND; timestamps must be timezone aware. ActionProposal, PolicyDecision and Execution
are independent, linked by proposal UUID. Policy computes effective risk from action kind.

No arbitrary passthrough fields, raw biometric arrays or non-finite confidence values are
accepted. Domain validation enforces invariants; persistence/recording/cloud policy must also
check authorization at execution time. Schema booleans alone do not establish real consent.

ActionProposal additionally accepts entity_create/entity_update; their effective policy risk
is audit. The manual registry execution boundary enforces ownership, immutable enrollment
fields and verified consent requirements beyond the schema (ADR-022).
