# AGENTS.md — Project Mnemos

Before modifying this repository, read `CODEX.md` in full.

1. Google Drive is canonical for approved requirements, governance, architecture and the operational plan.
2. `docs/source-of-truth/` is a local mirror/cache.
3. Respect task dependencies.
4. Task Done requires acceptance criteria, tests, applicable benchmarks, documentation and failure-path verification.
5. Epic Done requires all applicable tasks plus integrated verification.
6. Milestone Done requires end-to-end exit criteria.
7. Continue autonomously with the next unblocked work item.
8. Resolve reversible uncertainty by benchmark + ADR + decision; then continue.
9. Stop only for genuine external/irreversible blockers.
10. Keep project-generated data/models/cache/logs/media/DB/datasets/temp under `runtime/` whenever possible.
11. Keep `INSTALLATION_REGISTRY.md` and `DATA_LAYOUT.md` current.
12. Never bypass privacy, biometric, recording or Action Policy constraints.
13. The assistant is **Tobi**, always with an `i`.

14. For development, Sol only orchestrates while **only GPT-6 Luna** subagents execute scoped implementation/review/integration. Read `docs/runbooks/SOL_LUNA_ORCHESTRATION.md` and verify project agent config before delegating.

Primary goal: make Project Mnemos work completely, not merely scaffold it.
