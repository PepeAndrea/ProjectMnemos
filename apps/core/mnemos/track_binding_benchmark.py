"""Synthetic session association and SQLite audit overhead, not identity accuracy."""

import json
import tempfile
import time
from pathlib import Path
from uuid import UUID, uuid4

from .capture import CaptureSession
from .domain import Entity, Provenance, Retention
from .media import OpenCVVideoSource
from .registry import GovernedRegistry
from .runtime import RuntimeLayout
from .storage import EntityRepository
from .track_binding import authorize_binding
from .tracking import TrackUpdate
from .vision import Box, Detection


def main() -> None:
    layout = RuntimeLayout()
    layout.configure()
    samples: dict[str, list[float]] = {"claim_finish": [], "policy_audit": []}
    owner = uuid4()
    with tempfile.TemporaryDirectory(prefix="track-binding-", dir=layout.path("tmp")) as folder:
        repo = EntityRepository("sqlite:///" + str(Path(folder) / "benchmark.db"))
        repo.initialize()
        try:
            entity = GovernedRegistry(repo, owner).save(
                Entity(
                    kind="object",
                    name="Synthetic benchmark object",
                    enrolled=True,
                    confidence=1,
                    provenance=Provenance(source_id="synthetic-benchmark", method="human"),
                    retention=Retention(scope="persistent", purpose="synthetic benchmark"),
                )
            )
            capture = CaptureSession(
                OpenCVVideoSource(Path(folder) / "never-opened.avi"), None
            )  # never started, no device access
            capture.state = "running"
            for sequence in range(100):
                key = uuid4()
                detection = Detection("backpack", 0.9, Box(0, 0, 20, 20), "synthetic", sequence)
                capture.publish_tracks(
                    [TrackUpdate("enter", str(key), detection)], time.monotonic()
                )
                start = time.perf_counter()
                claim = capture.claim_track(key)
                assert capture.finish_binding(key, entity.id, claim["claim_id"])
                samples["claim_finish"].append((time.perf_counter() - start) * 1000)
                start = time.perf_counter()
                authorize_binding(repo, owner, UUID(capture.id), key, entity.id, confirmed=True)
                samples["policy_audit"].append((time.perf_counter() - start) * 1000)
            capture.clear_media()
            assert not capture.track_bindings
        finally:
            repo.close()
    report = {
        "passed": True,
        "scope": "100 synthetic associations, isolated SQLite audit; no recognition accuracy",
        "metrics": {
            name: {
                "samples": len(values),
                "p50_ms": sorted(values)[len(values) // 2],
                "p95_ms": sorted(values)[int(len(values) * 0.95) - 1],
            }
            for name, values in samples.items()
        },
    }
    layout.path("exports/track-binding-benchmark.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
