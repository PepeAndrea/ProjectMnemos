"""Deterministic safe A/V harness. Not a substitute for ML field validation."""

import json
import math
import struct
import wave
from pathlib import Path
from uuid import uuid4

from .domain import Event, Observation, Provenance
from .metrics import Metrics
from .runtime import ROOT, RuntimeLayout


def replay(fixture: Path, output: Path | None = None) -> dict[str, object]:
    data = json.loads(fixture.read_text())
    metrics = Metrics()
    lifecycle = []
    session = uuid4()
    for row in data["events"]:
        with metrics.measure("contract_replay"):
            observation = Observation(
                modality="video",
                session_id=session,
                confidence=1,
                provenance=Provenance(source_id=data["source"], method="fixture"),
            )
            event = Event(
                kind=row["kind"],
                observation_ids=[observation.id],
                confidence=1,
                provenance=observation.provenance,
            )
            lifecycle.append(event.kind)
    if lifecycle != data["expected_lifecycle"]:
        raise AssertionError("replay expected event mismatch")
    if output is not None:
        output.mkdir(parents=True, exist_ok=True)
        audio = data["audio"]
        samples = int(audio["sample_rate"] * audio["seconds"])
        with wave.open(str(output / "tone.wav"), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(audio["sample_rate"])
            stream.writeframes(
                b"".join(
                    struct.pack(
                        "<h",
                        int(
                            6000
                            * math.sin(
                                2 * math.pi * audio["frequency_hz"] * n / audio["sample_rate"]
                            )
                        ),
                    )
                    for n in range(samples)
                )
            )
        video = data["video"]
        for index in range(video["frames"]):
            header = f"P6\n{video['width']} {video['height']}\n255\n".encode()
            pixels = bytes([index * 30, 80, 100]) * video["width"] * video["height"]
            (output / f"frame-{index:03}.ppm").write_bytes(header + pixels)
    return {
        "fixture": fixture.name,
        "events": len(lifecycle),
        "passed": True,
        "metrics": metrics.report(),
        "scope": "synthetic contracts only",
    }


def main() -> None:
    layout = RuntimeLayout()
    layout.configure()
    result = replay(ROOT / "tests/fixtures/scenario.json", layout.path("datasets/synthetic"))
    target = layout.path("exports/foundation-benchmark.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
