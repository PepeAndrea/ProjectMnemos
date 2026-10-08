"""Durable one-shot temporal reminders with a transactional local notification inbox."""

import asyncio
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import JSON, DateTime, String, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Mapped, Session, mapped_column

from .domain import ActionExecution, ActionProposal, Provenance, Reminder, Risk
from .policy import Authorization, PolicyEngine
from .storage import Base, LocalActionRow
from .triggers import ready


class ReminderRow(Base):
    __tablename__ = "reminders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    state: Mapped[str] = mapped_column(String(16))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class NotificationRow(Base):
    __tablename__ = "notifications"
    # One inbox entry per one-shot reminder, even across restarts/concurrent ticks.
    reminder_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class TemporalScheduler:
    def __init__(self, engine: Engine, owner_id: UUID):
        self.engine, self.owner_id = engine, owner_id
        self.stop_event = asyncio.Event()
        self.task: asyncio.Task[None] | None = None
        self.error: str | None = None
        self.last_tick: str | None = None

    def authorize(
        self, kind: Literal["reminder", "notify"], params: dict[str, Any], source_id: UUID
    ) -> ActionExecution:
        proposal = ActionProposal(
            kind=kind,
            params=params,
            source_event_id=source_id,
            requested_by=self.owner_id,
            confidence=1,
            risk=Risk.AUDIT,
            provenance=Provenance(source_id="owner-temporal-scheduler", method="human"),
        )
        decision = PolicyEngine().evaluate(proposal, Authorization(self.owner_id, True))
        if not decision.allowed:
            raise PermissionError(decision.reason)
        return ActionExecution(
            proposal_id=proposal.id,
            status="succeeded",
            policy=decision,
            result={
                "kind": kind,
                "source_id": str(source_id),
                "proposal": proposal.model_dump(mode="json"),
            },
        )

    def create(self, reminder: Reminder) -> Reminder:
        trigger = reminder.trigger
        if reminder.state != "pending" or reminder.snooze_until is not None:
            raise ValueError("new reminder must be pending without snooze")
        if trigger.due_at is None or any([trigger.entity_visible, trigger.place, trigger.topic]):
            raise ValueError("temporal scheduler accepts time-only triggers")
        execution = self.authorize("reminder", reminder.model_dump(mode="json"), reminder.id)
        with Session(self.engine) as session, session.begin():
            if session.get(ReminderRow, str(reminder.id)) is not None:
                raise ValueError("reminder already exists")
            session.add(
                ReminderRow(
                    id=str(reminder.id),
                    state="pending",
                    due_at=trigger.due_at,
                    payload=reminder.model_dump(mode="json"),
                )
            )
            session.add(
                LocalActionRow(
                    id=str(execution.proposal_id),
                    created_at=execution.executed_at,
                    payload=execution.model_dump(mode="json"),
                )
            )
        return reminder

    def reminders(self, limit: int = 100) -> list[Reminder]:
        if not 1 <= limit <= 1000:
            raise ValueError("invalid query limit")
        with Session(self.engine) as session:
            rows = session.scalars(select(ReminderRow).order_by(ReminderRow.due_at).limit(limit))
            return [Reminder.model_validate(row.payload) for row in rows]

    def notifications(self, limit: int = 100) -> list[dict[str, Any]]:
        if not 1 <= limit <= 1000:
            raise ValueError("invalid query limit")
        with Session(self.engine) as session:
            rows = session.scalars(
                select(NotificationRow)
                .order_by(NotificationRow.created_at.desc(), NotificationRow.reminder_id)
                .limit(limit)
            )
            return [row.payload for row in rows]

    def tick(self, at: datetime | None = None) -> int:
        at = at or datetime.now(UTC)
        if at.tzinfo is None:
            raise ValueError("scheduler clock requires timezone")
        count = 0
        with Session(self.engine) as session, session.begin():
            rows = session.scalars(
                select(ReminderRow)
                .where(ReminderRow.state == "pending", ReminderRow.due_at <= at)
                .order_by(ReminderRow.due_at, ReminderRow.id)
                .limit(100)
                .with_for_update(skip_locked=True)
            )
            for row in rows:
                reminder = Reminder.model_validate(row.payload)
                if not ready(reminder, at, set()):
                    continue
                execution = self.authorize("notify", {"reminder_id": row.id}, reminder.id)
                # Insert, state change and authorization audit commit together. Failed delivery
                # rolls back to pending; inbox retrieval never runs an external side effect.
                session.add(
                    NotificationRow(
                        reminder_id=row.id,
                        created_at=at,
                        payload={
                            "reminder_id": row.id,
                            "text": reminder.text,
                            "created_at": at.isoformat(),
                            "urgency": reminder.urgency,
                        },
                    )
                )
                session.add(
                    LocalActionRow(
                        id=str(execution.proposal_id),
                        created_at=at,
                        payload=execution.model_dump(mode="json"),
                    )
                )
                reminder.state = "notified"
                row.state, row.payload = reminder.state, reminder.model_dump(mode="json")
                count += 1
        self.last_tick, self.error = at.isoformat(), None
        return count

    def start(self) -> None:
        self.task = asyncio.create_task(self.run())

    async def run(self) -> None:
        delay = 1.0
        while not self.stop_event.is_set():
            try:
                await asyncio.to_thread(self.tick)
                delay = 1.0
            except (ValueError, PermissionError):
                self.error = (
                    "reminder policy or stored contract invalid; pending reminders retained"
                )
                delay = min(30, delay * 2)
            except SQLAlchemyError:
                self.error = "reminder database unavailable; pending reminders retained"
                delay = min(30, delay * 2)
            try:
                await asyncio.wait_for(self.stop_event.wait(), delay)
            except TimeoutError:
                pass

    async def stop(self) -> None:
        self.stop_event.set()
        if self.task is not None:
            await self.task
