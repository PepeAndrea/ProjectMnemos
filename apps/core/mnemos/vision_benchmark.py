"""Measure cold/warm model execution locally, with safe blank inputs."""

import json
import platform
import resource
import time
from datetime import UTC, datetime

from .media import VideoFrame
from .metrics import Metrics
from .runtime import ROOT
from .vision import YOLOXProvider, YuNetProvider


def main() -> None:
    metrics = Metrics()
    frame = VideoFrame(
        "benchmark", 0, 0, datetime.now(UTC), 640, 480, "bgr24", bytes(640 * 480 * 3)
    )
    results = {}
    providers: list[tuple[str, YOLOXProvider | YuNetProvider]] = [
        ("yolox-s", YOLOXProvider()),
        ("yunet", YuNetProvider()),
    ]
    for name, provider in providers:
        start = time.perf_counter()
        assert provider.detect(frame) == []
        cold_ms = (time.perf_counter() - start) * 1000
        for _ in range(20):
            with metrics.measure(name):
                assert provider.detect(frame) == []
        provider.unload()
        results[name] = {"cold_ms": cold_ms, "unloaded": provider.model is None}
    report = {
        "hardware": "M1/8GB",
        "python": platform.python_version(),
        "scope": "blank-scene smoke, not accuracy",
        "providers": results,
        "metrics": metrics.report(),
        "process_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    path = ROOT / "runtime/exports/vision-benchmark.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
