# ADR-008: OpenAI Cloud Providers

**Status:** Accepted

## Decision
Use OpenAI through replaceable provider interfaces; typed decisions and reasoning separated.

## Consequences
Preserve replaceable contracts, test the decision on the official M1/8GB profile where applicable, and supersede via a new ADR if later evidence invalidates it.
