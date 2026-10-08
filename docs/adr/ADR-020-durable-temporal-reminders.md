# ADR-020 — Durable temporal reminders and a local inbox

Status: Accepted, 2026-10-08. Applies to T046, depending on verified T004.

Use a one-second in-process scheduler and the existing relational database. At most 100 due
rows are evaluated per tick. PostgreSQL FOR UPDATE SKIP LOCKED coordinates concurrent ticks;
one primary-key inbox entry per reminder suppresses duplicate delivery. Reminder state,
notification and ActionProposal/PolicyDecision/ActionExecution audit commit in one transaction.
Failure rolls back to pending. Restarts recover overdue rows; no Redis or external scheduler is
needed. Database outages produce visible status and backoff up to 30 seconds. PostgreSQL
connect/statement timeouts are bounded to five seconds. API owner auth gates creation and reads;
PolicyEngine authorizes both persistence and notify execution. These are one-shot temporal
reminders only; contextual triggers, interruption rules and snooze/dismiss flows remain separate.

Notifications are delivered to a durable local dashboard inbox, accessible after reconnect.
There is no OS push, sound, email or third-party messaging. Closing the browser leaves scheduled
reminders active, as explicit persistent prospective memory. No transcript or media is stored.

Tests verify clock/timezone, pre-deadline behavior, restart, duplicates, failed inbox transaction,
audit, missing DB, API auth/validation and concurrent PostgreSQL workers. A disposable isolated
PostgreSQL schema prevents the concurrency test from processing installation reminders.
Live core HTTP verified notification availability ~566ms after deadline. Synthetic SQLite M1
benchmark: creation p95 ~1.03ms; 100 due rows ~11.97ms; idle tick p95 ~0.234ms. This supports a
simple scheduler for the MVP; these SQLite timings do not estimate PostgreSQL throughput.
