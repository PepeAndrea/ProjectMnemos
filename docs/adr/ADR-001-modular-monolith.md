# ADR-001: Modular Monolith

**Status:** Accepted

## Decision
Use a modular monolith with bounded in-process events; distribute only after measured need.

## Consequences
Preserve replaceable contracts, test the decision on the official M1/8GB profile where applicable, and supersede via a new ADR if later evidence invalidates it.
