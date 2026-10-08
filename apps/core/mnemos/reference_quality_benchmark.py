"""Synthetic diagnostics and bounded-vs-full measurement spike, never identity calibration."""

import importlib
import json
import time

from .reference_quality import inspect_crop
from .runtime import RuntimeLayout


def main() -> None:
    cv, np = importlib.import_module("cv2"), importlib.import_module("numpy")
    checker = ((np.indices((128, 128)).sum(axis=0) // 8) % 2 * 180 + 35).astype(np.uint8)
    sharp = np.repeat(checker[:, :, None], 3, axis=2)
    fixtures = {
        "sharp-pattern": sharp,
        "blurred-pattern": cv.GaussianBlur(sharp, (31, 31), 10),
        "plain-color": np.full((128, 128, 3), [20, 90, 40], dtype=np.uint8),
        "black-no-signal": np.zeros((128, 128, 3), dtype=np.uint8),
        "white-no-signal": np.full((128, 128, 3), 255, dtype=np.uint8),
        "large-pattern": cv.resize(sharp, (1600, 1600)),
    }
    report = {}
    for name, crop in fixtures.items():
        timings, outcome = [], None
        for _ in range(50):
            start = time.perf_counter()
            try:
                outcome = inspect_crop(crop)
            except ValueError:
                outcome = {"rejected": True}
            timings.append((time.perf_counter() - start) * 1000)
        assert outcome is not None
        if "no-signal" in name:
            assert outcome.get("rejected")
        if name == "plain-color":
            assert "low-contrast" in outcome["warnings"]
        if name == "sharp-pattern":
            assert outcome["warnings"] == []
        report[name] = {"samples": 50, "p95_ms": sorted(timings)[47], "diagnostics": outcome}
    # Alternative spike only: measure all 1600px pixels rather than the bounded 256px
    # sample. The algorithm is deliberately identical, without enabling a runtime flag.
    timings = []
    full = fixtures["large-pattern"]
    for _ in range(50):
        start = time.perf_counter()
        gray = cv.cvtColor(full, cv.COLOR_BGR2GRAY)
        float_pixels = gray.astype(np.float32)
        _metrics = (
            float(gray.mean()),
            float(gray.std()),
            float(np.abs(np.diff(float_pixels, axis=0)).mean()),
            float(np.abs(np.diff(float_pixels, axis=1)).mean()),
            float(((gray <= 5) | (gray >= 250)).mean()),
        )
        timings.append((time.perf_counter() - start) * 1000)
    output = {
        "passed": True,
        "scope": "six generated crops; measurement overhead/diagnostic behaviors only, not representative quality or recognition accuracy",
        "fixtures": report,
        "full_resolution_alternative": {
            "samples": 50,
            "p95_ms": sorted(timings)[47],
            "pixels": 1600 * 1600,
        },
        "bounded_sample_pixels": 256 * 256,
    }
    layout = RuntimeLayout()
    layout.configure()
    layout.path("exports/reference-quality-benchmark.json").write_text(
        json.dumps(output, indent=2) + "\n"
    )
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
