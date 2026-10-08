"""Synthetic consent/encryption/access/revocation cost, no real biometrics."""

import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from .biometrics import BiometricKey, PersonEnrollment
from .metrics import Metrics
from .runtime import RuntimeLayout
from .storage import EntityRepository


def main() -> None:
    layout = RuntimeLayout()
    layout.configure()
    metrics = Metrics()
    with tempfile.TemporaryDirectory(dir=layout.path("tmp"), prefix="biometric-benchmark-") as temp:
        repo = EntityRepository("sqlite:///" + str(Path(temp) / "vault.db"))
        repo.initialize()
        service = PersonEnrollment(repo, uuid4(), BiometricKey(Path(temp) / "private" / "key"))
        try:
            for _ in range(50):
                with metrics.measure("grant"):
                    entity = service.grant(
                        "Synthetic benchmark subject",
                        face=True,
                        voice=False,
                        subject_permission_attested=True,
                        expires_at=datetime.now(UTC) + timedelta(days=1),
                    )
                consent_id = UUID(service.status(entity.id)["id"])
                with metrics.measure("encrypt_audit"):
                    key = service.store(
                        consent_id,
                        "face",
                        tuple([1.0] + [0.0] * 127),
                        "synthetic-v1",
                        confirmed=True,
                    )
                with metrics.measure("decrypt_audit"):
                    assert service.read(key)[0] == 1
                with metrics.measure("revoke_purge_audit"):
                    service.revoke(entity.id, entity.name, confirmed=True)
            assert repo.list() == []
        finally:
            repo.close()
    report = {
        "passed": True,
        "scope": "50 synthetic 128-dimensional vectors, isolated SQLite; no identity quality claim",
        "metrics": metrics.report(),
    }
    layout.path("exports/biometric-benchmark.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
