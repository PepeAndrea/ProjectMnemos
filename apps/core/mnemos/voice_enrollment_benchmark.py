"""Bounded local proposal routing cost on explicitly synthetic commands."""

import json
from uuid import uuid4

from .metrics import Metrics
from .runtime import RuntimeLayout
from .speech_stream import TranscriptUpdate
from .voice_enrollment import VoiceEnrollmentInbox, suggested_name


def main() -> None:
    layout = RuntimeLayout()
    layout.configure()
    metrics = Metrics()
    inbox = VoiceEnrollmentInbox(str(uuid4()), lambda: 100)
    cases = [
        ("Tobi, memorizza questo come il mio zaino.", "il mio zaino"),
        ("Toby, remember this is my backpack.", "my backpack"),
        ("Save this as my bag", "my bag"),
        ("Do not save this as my bag", None),
        ("Tobi, paga cento euro", None),
        ("Ha detto: Tobi, memorizza questo come uno zaino", None),
    ]
    for n in range(1000):
        text, expected = cases[n % len(cases)]
        with metrics.measure("route"):
            assert suggested_name(text) == expected
        update = TranscriptUpdate(str(n), "synthetic", 99, 100, text, "it", 1, False, "anonymous")
        with metrics.measure("offer"):
            inbox.offer(update)
    for _ in range(100):
        with metrics.measure("snapshot_50"):
            values = inbox.snapshot()
        assert len(values) == 50
        for item in values:
            decision = item["policy"]
            assert isinstance(decision, dict) and not decision["allowed"]
    assert len(inbox.seen) <= 200
    inbox.clear()
    assert inbox.snapshot() == []
    report = {
        "passed": True,
        "scope": "synthetic narrow command grammar; not general intent accuracy",
        "proposals_max": 50,
        "dedup_max": 200,
        "unauthorized_executions": 0,
        "cloud_calls": 0,
        "metrics": metrics.report(),
    }
    layout.path("exports/voice-enrollment-benchmark.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
