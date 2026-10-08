import json
import wave
from pathlib import Path

import pytest
from mnemos.metrics import Metrics, classification
from mnemos.replay import replay


def test_safe_av_replay(tmp_path):
    result = replay(Path("tests/fixtures/scenario.json"), tmp_path)
    assert result["passed"]
    with wave.open(str(tmp_path / "tone.wav")) as stream:
        assert stream.getframerate() == 16000
        assert stream.getnframes() == 64000
    assert len(list(tmp_path.glob("*.ppm"))) == 4


def test_bad_expected_events(tmp_path):
    data = json.loads(Path("tests/fixtures/scenario.json").read_text())
    data["expected_lifecycle"] = ["exit"]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    with pytest.raises(AssertionError):
        replay(path)


def test_metrics_bounded_and_identity_measurement():
    metrics = Metrics(10)
    for n in range(100):
        metrics.observe("stage", n)
    assert metrics.report()["stage"] == {"samples": 10, "p50_ms": 94, "p95_ms": 99}
    assert classification(["a", "b", "unknown"], ["a", "a", "c"])["false_identity_rate"] == 2 / 3
    with pytest.raises(ValueError):
        metrics.observe("stage", float("nan"))
