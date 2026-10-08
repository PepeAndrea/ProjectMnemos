# Sol → Luna Parallel Delivery Protocol

## Scope and intent
This is a repository execution policy, not a change to the functional requirements. The canonical Project Mnemos product and roadmap documents remain on Google Drive. The assistant is **Tobi**.

**Root agent:** GPT-6 Sol, orchestrator/technical lead/acceptance authority.
**Only spawned worker models:** GPT-6 Luna, pinned in project-scoped `.codex/config.toml` and each role file.
**No other model may be spawned for project work** unless a human explicitly authorizes changing this architecture.
**Sol does not directly implement application code or execute edits.** It performs planning, delegation, arbitration, review decisions, task prioritization and milestone acceptance. Implementation, fixes, test execution, integration and status update preparation are delegated to Luna agents.

Codex's supported delegation model is a runtime capability; project TOML and these instructions are respected only in trusted/local Codex environments that load `.codex` settings. If the client does not support custom subagents or model pinning, STOP the multi-agent launch rather than silently spawning Sol workers.

## Reconcile progress before dispatch
Project implementation is already in progress. Do NOT assume the `Tasks` CSV still reflects reality.
1. Check the actual working tree, branch, uncommitted changes and commits since source snapshot.
2. Compare working features and tests to canonical acceptance criteria.
3. Produce `IMPLEMENTATION_STATUS.md` with Verified Done, Implemented-Unverified, In Progress, Not Started, and Blocked.
4. Do not reset, recreate, overwrite or reimplement working code simply because it is absent from the remote main branch.
5. Reconcile with Google Drive statuses when authorized. Never claim a task Done solely from self-report or scaffold.
6. Identify prerequisite contracts/schema changes before parallelizing their consumers.

## Dispatch strategy
Use at most **3 concurrent Luna agent threads**, excluding Sol. This limit controls agent threads, not simultaneous GPU/CPU/DB-heavy work. Recommended waves:
- Discovery: 1 Luna explorer + 1 Luna reviewer inspecting test/contract coverage in parallel (read-only).
- Implementation: 2 independent Luna implementers; reserve a slot for review/integration when useful.
- Quality gate: an independent Luna reviewer, then Luna integrator; both can be reused for next tasks.

Do not spawn two write workers merely to use all slots. Parallelism is conditional on non-overlapping files, contracts and infrastructure state.

## Ownership and isolation
Preferred: one feature branch + separate Git worktree per write task (or Codex-managed independent worktrees).
Task examples:
- `codex/m1-webrtc-sensor` owns phone A/V gateway UI and dedicated transport adapter;
- `codex/m2-instance-matching` owns instance resolver and dedicated test fixtures.

A shared workspace is **not** an isolated worktree. If the client spawns subagents into the same checkout, only run parallel read-only work or assignments with explicitly disjoint file ownership; otherwise serialize writers.
Never simultaneously modify shared contracts, OpenAPI/generated types, migrations, package locks, `CODEX.md`, plan CSVs, deployment configs or `runtime/data/postgres`.
Changes to a shared contract must be implemented and integrated first; only then start consumers against the same version.
One worker owns each file in an active wave.
Heavy ML benchmarks and DB migrations run sequentially on the M1 8 GB target.

## Task packet required from Sol
Use `docs/runbooks/LUNA_TASK_PACKET_TEMPLATE.md`.
Every worker receives:
- Task ID, Epic, Milestone and why it is unblocked;
- current branch/commit, worktree, allowed edit paths and forbidden paths;
- exact Google Drive/local mirror and ADR references;
- current implementation state and known dependencies;
- inputs, outputs, typed contracts and expected error paths;
- acceptance criteria and Definition of Done;
- test commands and hardware/runtime limits;
- output artifact, commit strategy and handoff fields;
- explicit stop/escalation conditions.

Do not pass vague directions such as "implement memory". Decompose into bounded independent deliverables first.

## Workflow for one wave
1. **Sol** reads canonical priorities, status and dependencies; uses a Luna explorer for unfamiliar code.
2. **Sol** freezes shared interfaces and prepares non-overlapping task packets.
3. **Sol** spawns independent Luna implementers with role `luna_implementer`, each constrained to task-owned worktrees.
4. **Luna workers** code, add tests, perform focused checks and return concise evidence.
5. **Sol** sends each artifact to a different `luna_reviewer`; review checks task acceptance and regressions.
6. **Sol** returns defects to original workers for fixes.
7. **Luna integrator** integrates approved changes, executes aggregate tests and reports results; never merges blind.
8. **Sol** verifies completion criteria, updates the local progress report and delegates authorized plan synchronization. Then starts the next unblocked wave.
9. Milestone exit checks are independently verified end-to-end; unchecked items remain open.

## Evidence and status
Minimum task handoff:
- task ID and scope;
- branch/commit SHA and changed files;
- executed tests with pass/fail outputs (not claimed without running);
- performance/accuracy evidence where applicable;
- privacy/security/license checklist;
- reviewer disposition and unresolved issues;
- integration commit and full-suite result;
- status proposed: `Done` only if objectively verified.

Sol must avoid declaring all Done just to satisfy a long-running Goal. Maintain `BLOCKERS.md` for genuine blockers, with actionable requests.

## Model and runtime behavior
- Root model configured as `gpt-6-sol`. If you intentionally select an available newer Sol in your Codex composer, this policy still requires a Sol root and Luna-only children.
- Child default model `gpt-6-luna`; all custom child roles explicitly pin `gpt-6-luna`.
- Child effort `high`. Root effort `high`. Adjust root reasoning within supported levels only when necessary.
- Confirm `/status` and `/debug-config` before the first run. The repo must be trusted, otherwise project config is ignored.
- If a spawned agent appears as Sol rather than Luna, stop delegation and correct effective config before resuming.
- Never enable permissive unattended destructive commands or elevated permissions merely to keep work flowing.

## First wave for an existing partial implementation
Before any new feature, perform a **read-only audit of actual progress**:
1. Luna explorer maps modules, tests, branch and existing code to all 96 task IDs.
2. Luna reviewer separately identifies correctness/security/acceptance gaps and missing E2E paths.
3. Sol resolves task states, shared interface bottlenecks and unblocked parallel candidates.
4. Only then launch a wave of independent Luna implementers.

Suggested parallel slots after audit: one task in media ingestion/browser-phone; one in core/entity/memory, **only if** no shared contract/data migration collision. Otherwise run one implementer + reviewer.
