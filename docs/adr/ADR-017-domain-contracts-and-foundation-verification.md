# ADR-017: Versioned domain contracts and foundation verification

Status: Accepted (reversible implementation decision), 2026-10-08.

Problem: the bootstrap lacked executable domain contracts, privacy boundaries and replay checks.
Options: untyped dicts; handwritten JSON Schema; Pydantic v2 contracts with generated JSON Schema.
Decision: Pydantic v2, schema_version=1, reject extra fields, finite scores in [0,1], timezone
aware provenance and ordered source timecodes. Use UUID references for evidence and embeddings;
public Entity contains no raw biometric template. Persistent people require explicit enrollment
and consent, while unknown/session tracks remain volatile. Observation, Event and Memory are
separate types. Partial transcripts cannot reference persistent audio.

SQLAlchemy entity registry targets PostgreSQL. SQLite is limited to isolated contract tests;
a separate opt-in integration verifies PostgreSQL and pgvector. Alembic controls runtime schema.
Owner bearer authentication fails closed when absent/short, and no sensor starts on import.
Models cannot assign their own effective action risk. Confirmation and authorization remain
outside ActionProposal, and unsupported actions are denied.

Synthetic A/V replay validates clocks, schemas and harness plumbing without collecting private
media. It cannot establish perception accuracy. Benchmarks on real licensed fixtures and live
M1/phone tests remain necessary before perception milestones are Done.

Evidence: foundation unit/contract/API suite plus real PostgreSQL/pgvector integration; see
docs/verification/foundation.md. Low latency contract replay supports this choice but says
nothing about ML latency. Revisit schemas via versioned migrations when concrete provider
integration requires fields; never silently expand privacy retention.
