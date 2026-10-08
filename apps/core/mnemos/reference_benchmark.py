"""Contained synthetic crop/media/audit timing; no detector identity quality claim."""

import json
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from .biometrics import BiometricKey, PersonEnrollment
from .capture import CaptureSession
from .domain import Entity, Provenance, Retention
from .face_references import FaceReferences
from .media import OpenCVVideoSource, VideoFrame
from .references import ObjectReferences
from .registry import GovernedRegistry
from .runtime import RuntimeLayout
from .storage import EntityRepository
from .tracking import TrackUpdate
from .vision import Box, Detection


def main(face: bool = False) -> None:
    layout = RuntimeLayout()
    layout.configure()
    times: dict[str, list[float]] = {
        name: [] for name in ("crop", "store_audit", "read_audit", "retire_purge_audit")
    }
    with tempfile.TemporaryDirectory(
        prefix="reference-benchmark-", dir=layout.path("tmp")
    ) as folder:
        root = Path(folder)
        repo = EntityRepository("sqlite:///" + str(root / "refs.db"))
        repo.initialize()
        try:
            owner = uuid4()
            entity = (
                PersonEnrollment(
                    repo, owner, BiometricKey(root / "private" / "unused-vector-key")
                ).grant(
                    "Synthetic face-box benchmark",
                    face=True,
                    voice=False,
                    subject_permission_attested=True,
                    expires_at=datetime.now(UTC) + timedelta(hours=2),
                )
                if face
                else GovernedRegistry(repo, owner).save(
                    Entity(
                        kind="object",
                        name="Synthetic benchmark crop",
                        enrolled=True,
                        confidence=1,
                        provenance=Provenance(source_id="synthetic", method="human"),
                        retention=Retention(scope="persistent", purpose="explicit benchmark"),
                    )
                )
            )
            service = (
                FaceReferences(repo, owner, RuntimeLayout(root))
                if face
                else ObjectReferences(repo, owner, RuntimeLayout(root))
            )
            capture = CaptureSession(OpenCVVideoSource(root / "never-opened.avi"), None)
            capture.state = "running"
            track = uuid4()
            detection = Detection(
                "face" if face else "backpack", 0.9, Box(40, 40, 128, 128), "synthetic", 1
            )
            for _ in range(50):
                capture.publish_tracks(
                    [TrackUpdate("update", str(track), detection)], time.monotonic()
                )
                if not face:
                    capture.track_bindings[str(track)] = str(entity.id)
                capture.reference_frame = VideoFrame(
                    "synthetic",
                    1,
                    time.monotonic(),
                    datetime.now(UTC),
                    256,
                    256,
                    "bgr24",
                    bytes([20, 90, 40]) * (256 * 256),
                )
                start = time.perf_counter()
                jpeg, provenance = (
                    capture.face_crop(track) if face else capture.object_crop(track, entity.id)
                )
                times["crop"].append((time.perf_counter() - start) * 1000)
                start = time.perf_counter()
                key = service.store(
                    entity.id,
                    jpeg,
                    provenance,
                    datetime.now(UTC) + timedelta(hours=1),
                    confirmed=True,
                    confirmed_name=entity.name if face else None,
                )
                times["store_audit"].append((time.perf_counter() - start) * 1000)
                start = time.perf_counter()
                assert service.read(key) == jpeg
                times["read_audit"].append((time.perf_counter() - start) * 1000)
                start = time.perf_counter()
                service.retire(key, entity.name, confirmed=True)
                assert service.cleanup() == 1
                times["retire_purge_audit"].append((time.perf_counter() - start) * 1000)
            assert repo.get(entity.id).reference_ids == [] and not list(
                service.folder.glob("*.enc")
            )
        finally:
            repo.close()
    report = {
        "passed": True,
        "scope": "50 generated 128px face-box crops with consent checks; no real subject or identity calibration"
        if face
        else "50 synthetic 128px crops, encrypted local files and isolated SQLite; no identity quality claim",
        "metrics": {
            name: {
                "samples": len(values),
                "p50_ms": sorted(values)[len(values) // 2],
                "p95_ms": sorted(values)[int(len(values) * 0.95) - 1],
            }
            for name, values in times.items()
        },
    }
    output = "face-reference-benchmark.json" if face else "reference-benchmark.json"
    layout.path("exports/" + output).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
