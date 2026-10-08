"""Bounded measurements; no private text or media in metric labels."""

from collections import defaultdict, deque
from collections.abc import Iterator
from contextlib import contextmanager
from math import ceil, isfinite
from time import perf_counter


class Metrics:
    def __init__(self, max_samples: int = 1000):
        if max_samples < 1:
            raise ValueError("positive sample limit required")
        self.samples: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=max_samples))
        self.counters: dict[str, int] = defaultdict(int)

    def observe(self, name: str, milliseconds: float) -> None:
        if not isfinite(milliseconds) or milliseconds < 0:
            raise ValueError("invalid latency")
        self.samples[name].append(milliseconds)

    @contextmanager
    def measure(self, stage: str) -> Iterator[None]:
        start = perf_counter()
        try:
            yield
        finally:
            self.observe(stage, (perf_counter() - start) * 1000)

    def report(self) -> dict[str, dict[str, float | int]]:
        return {
            name: {
                "samples": len(values),
                "p50_ms": sorted(values)[ceil(len(values) * 0.5) - 1],
                "p95_ms": sorted(values)[ceil(len(values) * 0.95) - 1],
            }
            for name, values in self.samples.items()
            if values
        }


def classification(expected: list[str], predicted: list[str]) -> dict[str, float | int]:
    if not expected or len(expected) != len(predicted):
        raise ValueError("aligned nonempty labels required")
    true_positives = sum(e == p and e != "unknown" for e, p in zip(expected, predicted))
    false_positives = sum(e != p and p != "unknown" for e, p in zip(expected, predicted))
    false_negatives = sum(e != p and e != "unknown" for e, p in zip(expected, predicted))
    return {
        "precision": true_positives / max(1, true_positives + false_positives),
        "recall": true_positives / max(1, true_positives + false_negatives),
        "false_identity_rate": false_positives / len(expected),
        "cases": len(expected),
    }
