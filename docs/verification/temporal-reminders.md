# T046 acceptance evidence — 2026-10-08

Acceptance: owner creates a time-only reminder; nothing is delivered early; due/overdue reminder
produces one durable local notification; restart recovers pending work; failures preserve pending
state; notification and authorization audit are atomic. Batch/response sizes are bounded.

Implementation: scheduler.py, migration 0002_temporal_reminders, owner-only /reminders,
/notifications and /scheduler/status. The dashboard displays pending reminders and local inbox.

Evidence: tests/test_scheduler.py and tests/test_api.py. Four simultaneous PostgreSQL ticks over
20 isolated synthetic rows yielded 20 inbox entries total; no duplicates. Simulated insert
failure rolled back state/inbox/audit, and retry succeeded. Missing DB status remained visible
and scheduler stopped cleanly. Restart/aware deadlines/API unauthorized and duplicate failures
passed. Live core + PostgreSQL HTTP: notification available ~565.7ms after deadline, below the
provisional two-second one-shot delivery budget. Synthetic HTTP test data was cleaned afterward.

Reproduce: apply Alembic head, run scripts/check with MNEMOS_TEST_MODELS and
MNEMOS_TEST_POSTGRES opt-ins, then python -m mnemos.scheduler_benchmark. Benchmark uses a
separate temporary runtime SQLite DB and removes it. 100 creations p95 ~1.03ms; one 100-row due
batch ~11.97ms; 100 idle ticks p95 ~0.234ms; duplicate count 0. Reports under runtime/exports.

Temporal notifications are local dashboard delivery. Context recognition, interruption policy,
OS notifications, snooze/dismiss and voice extraction have separate task dependencies and are
not claimed here. T046 can be Done; E16/M5 cannot be Done until their remaining tasks/integrated
exit criteria pass. No milestone is declared complete.
