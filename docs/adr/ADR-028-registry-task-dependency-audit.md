# ADR-028 — Registry acceptance and downstream acquisition dependencies

Accepted 2026-10-08. Corrects the allocation of remaining T017 work in ADR-022–027;
does not remove a deliverable from the overall Mnemos goal.

Canonical plan row T017 states “Entity CRUD e enrollment — Creazione manuale/vocale
di persone e oggetti autorizzati”, dependency T001. E06 describes registry CRUD,
enrollment and metadata. T018 separately requires multiple object/person views and
quality checks, and depends on T017. T020 is registered-person face embedding matching;
T027 is authorized speaker embedding enrollment, also dependent on T017. Requiring
these downstream tasks to finish before T017 would create a circular exit condition.

Accept T017's registry deliverable after verified manual/voice-reviewed creation,
authenticated read/update and dedicated deletion/revocation with consent, expiry,
policy/audit and failure checks. Actual multiview acquisition, provider embeddings,
identity calibration and repeatable physical recognition remain mandatory in their
canonical tasks and milestone exits. This is a correction to implementation notes,
not a change to those requirements. No epic, milestone or full product slice is Done.

Evidence is audited in docs/verification/registry-acceptance.md, including real Whisper,
HTTP and PostgreSQL flows plus isolated browser corrections/reload/privacy checks.
Reversible transaction/registry choices already have the ADR-022–027 benchmarks.

The later request for automatic person approval remains an additional open work item
in the local operational ledger with scope clarification pending. Registry acceptance
does not claim that feature exists or waive subject consent/Action Policy. The current
explicit-review flow remains in force until its scoped replacement is implemented and
verified. This request remains part of the active overall goal.

All five canonical Drive modified timestamps were rechecked and match the verified
mirror. No canonical file/plan was modified or pushed by this acceptance decision.
