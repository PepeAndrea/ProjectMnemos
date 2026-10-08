"""Synthetic atomic enrollment/audit cost; never writes installation entities."""

import json
import platform
import tempfile
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .domain import Entity, Provenance, Retention
from .metrics import Metrics
from .registry import GovernedRegistry
from .runtime import RuntimeLayout
from .storage import EntityRepository, LocalActionRow


def main() -> None:
    layout = RuntimeLayout()
    layout.configure()
    metrics = Metrics()
    with tempfile.TemporaryDirectory(dir=layout.path("tmp"), prefix="registry-benchmark-") as temp:
        repo = EntityRepository("sqlite:///" + str(Path(temp) / "registry.db"))
        repo.initialize()
        registry = GovernedRegistry(repo, uuid4())
        try:
            values = []
            for _ in range(100):
                entity = Entity(
                    kind="object",
                    name="Synthetic benchmark object",
                    confidence=1,
                    enrolled=True,
                    provenance=Provenance(source_id="benchmark", method="synthetic"),
                    retention=Retention(scope="persistent", purpose="synthetic benchmark"),
                )
                with metrics.measure("policy_create_audit"):
                    entity = registry.save(entity)
                entity.name = "Synthetic correction"
                with metrics.measure("policy_update_audit"):
                    registry.save(entity, create=False)
                values.append(entity)
            assert len(repo.list()) == 100
            with Session(repo.engine) as session:
                assert session.scalar(select(func.count()).select_from(LocalActionRow)) == 200
            for entity in values:
                with metrics.measure("policy_delete_audit"):
                    registry.delete(entity.id, entity.name, True)
            assert repo.list() == []
            with Session(repo.engine) as session:
                assert session.scalar(select(func.count()).select_from(LocalActionRow)) == 300
        finally:
            repo.close()
    result = {
        "passed": True,
        "scope": "synthetic isolated SQLite; not PostgreSQL throughput",
        "hardware": platform.machine(),
        "entities": 100,
        "atomic_audits": 300,
        "metrics": metrics.report(),
    }
    layout.path("exports/registry-benchmark.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
