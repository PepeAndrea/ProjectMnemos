"""Synthetic resource benchmark; no camera, microphone or private data."""

import json
import platform
import time

from .metrics import Metrics
from .runtime import ROOT, BoundedQueue, MediaChunk, RollingBuffer


def main() -> None:
    metrics = Metrics(10000)
    buffer = RollingBuffer(seconds=300, max_bytes=1024 * 1024)
    queue = BoundedQueue[int](4)
    payload = b"\x00" * 640
    started = time.perf_counter()
    for n in range(20000):
        with metrics.measure("buffer_append"):
            buffer.append(MediaChunk(n * 0.02, payload))
        with metrics.measure("queue_put"):
            queue.put(n)
    elapsed = time.perf_counter() - started
    assert buffer.bytes_used <= buffer.max_bytes
    assert queue.queue.qsize() == 4 and queue.dropped == 19996
    assert buffer.chunks[0].timestamp >= buffer.latest - 300
    result = {
        "scope": "synthetic resource benchmark, not ML accuracy or phone E2E",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "iterations": 20000,
        "elapsed_seconds": elapsed,
        "buffer_bytes": buffer.bytes_used,
        "budget_bytes": buffer.max_bytes,
        "queue_capacity": 4,
        "drops": queue.dropped,
        "metrics": metrics.report(),
        "passed": True,
    }
    path = ROOT / "runtime/exports/resource-benchmark.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
