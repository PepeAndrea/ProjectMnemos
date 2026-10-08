import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from mnemos.domain import Provenance, Reminder, Trigger
from mnemos.scheduler import LocalActionRow, NotificationRow, TemporalScheduler
from mnemos.storage import EntityRepository
from sqlalchemy import event, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


def make_reminder(at):
    return Reminder(
        text="Synthetic temporal reminder",
        trigger=Trigger(due_at=at),
        provenance=Provenance(source_id="test-owner", method="synthetic"),
    )


def test_timezones_restart_duplicate_suppression_and_audit(tmp_path):
    at = datetime.now(UTC)
    repo = EntityRepository("sqlite:///" + str(tmp_path / "reminders.db"))
    repo.initialize()
    owner = uuid4()
    scheduler = TemporalScheduler(repo.engine, owner)
    reminder = make_reminder(at + timedelta(hours=1))
    scheduler.create(reminder)
    assert scheduler.tick(at) == 0
    with pytest.raises(ValueError):
        scheduler.create(reminder)
    with pytest.raises(ValueError):
        scheduler.tick(at.replace(tzinfo=None))
    repo.close()
    fresh = EntityRepository("sqlite:///" + str(tmp_path / "reminders.db"))
    scheduler = TemporalScheduler(fresh.engine, owner)
    assert scheduler.tick(at + timedelta(hours=2)) == 1
    assert scheduler.tick(at + timedelta(hours=3)) == 0
    assert scheduler.reminders()[0].state == "notified"
    assert len(scheduler.notifications()) == 1
    with Session(fresh.engine) as session:
        audit = list(session.scalars(select(LocalActionRow)))
        assert len(audit) == 2
        assert all(row.payload["policy"]["allowed"] for row in audit)
    contextual = make_reminder(at)
    contextual.trigger.place = "office"
    with pytest.raises(ValueError):
        scheduler.create(contextual)
    fresh.close()


def test_inbox_failure_rolls_back_state_and_retries(tmp_path):
    repo = EntityRepository("sqlite:///" + str(tmp_path / "retry.db"))
    repo.initialize()
    scheduler = TemporalScheduler(repo.engine, uuid4())
    scheduler.create(make_reminder(datetime.now(UTC)))

    def fail(mapper, connection, target):
        raise SQLAlchemyError("simulated inbox failure")

    event.listen(NotificationRow, "before_insert", fail)
    try:
        with pytest.raises(SQLAlchemyError):
            scheduler.tick()
        assert scheduler.reminders()[0].state == "pending"
        assert scheduler.notifications() == []
        with Session(repo.engine) as session:
            assert session.scalar(select(func.count()).select_from(LocalActionRow)) == 1
    finally:
        event.remove(NotificationRow, "before_insert", fail)
    assert scheduler.tick() == 1
    repo.close()


def test_background_scheduler_reports_database_failure_and_stops(tmp_path):
    async def run():
        repo = EntityRepository("sqlite:///" + str(tmp_path / "uninitialized.db"))
        scheduler = TemporalScheduler(repo.engine, uuid4())
        scheduler.start()
        for _ in range(100):
            if scheduler.error:
                break
            await asyncio.sleep(0.01)
        assert scheduler.error
        await scheduler.stop()
        assert scheduler.task.done()
        repo.close()

    asyncio.run(run())


@pytest.mark.skipif(not os.environ.get("MNEMOS_TEST_POSTGRES"), reason="real PostgreSQL opt-in")
def test_postgres_concurrent_ticks_deliver_once():
    repo = EntityRepository(os.environ["MNEMOS_TEST_POSTGRES"])
    from mnemos.storage import Base
    from sqlalchemy.schema import CreateSchema, DropSchema

    schema = "test_scheduler_" + uuid4().hex
    with repo.engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    isolated = repo.engine.execution_options(schema_translate_map={None: schema})
    Base.metadata.create_all(isolated)
    scheduler = TemporalScheduler(isolated, uuid4())
    reminders = [make_reminder(datetime.now(UTC)) for _ in range(20)]
    ids = [str(reminder.id) for reminder in reminders]
    try:
        for reminder in reminders:
            scheduler.create(reminder)
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert sum(pool.map(lambda _: scheduler.tick(), range(4))) == 20
        with Session(isolated) as session:
            inbox = list(
                session.scalars(select(NotificationRow).where(NotificationRow.reminder_id.in_(ids)))
            )
            assert len(inbox) == 20
        assert scheduler.tick() == 0
    finally:
        with repo.engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        repo.close()
