"""Reproducible synthetic scheduler benchmark in an isolated runtime SQLite database."""

import json
import platform
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .domain import Provenance, Reminder, Trigger
from .metrics import Metrics
from .runtime import RuntimeLayout
from .scheduler import TemporalScheduler
from .storage import EntityRepository


def main() -> None:
    layout = RuntimeLayout()
    layout.configure()
    metrics = Metrics()
    with tempfile.TemporaryDirectory(dir=layout.path("tmp"), prefix="scheduler-benchmark-") as temp:
        repo = EntityRepository("sqlite:///" + str(Path(temp) / "scheduler.db"))
        repo.initialize()
        scheduler = TemporalScheduler(repo.engine, uuid4())
        try:
            for _ in range(100):
                reminder = Reminder(
                    text="Synthetic benchmark fixture",
                    trigger=Trigger(due_at=datetime.now(UTC)),
                    provenance=Provenance(source_id="benchmark", method="synthetic"),
                )
                with metrics.measure("create"):
                    scheduler.create(reminder)
            with metrics.measure("due_batch_100"):
                assert scheduler.tick() == 100
            for _ in range(100):
                with metrics.measure("idle_tick"):
                    assert scheduler.tick() == 0
            assert len(scheduler.notifications()) == 100
        finally:
            repo.close()
    result = {
        "passed": True,
        "scope": "isolated SQLite scheduling/audit; not PostgreSQL throughput",
        "hardware": platform.machine(),
        "python": platform.python_version(),
        "reminders": 100,
        "duplicates": 0,
        "max_tick_batch": 100,
        "metrics": metrics.report(),
    }
    layout.path("exports/scheduler-benchmark.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
