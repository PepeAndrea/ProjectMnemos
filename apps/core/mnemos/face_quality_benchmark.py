"""Generated patterns/points only: diagnostic overhead, never face accuracy."""

import importlib
import json
import time
from typing import Any

from .face_quality import inspect_face_crop
from .runtime import RuntimeLayout


def main() -> None:
    cv, np = importlib.import_module("cv2"), importlib.import_module("numpy")
    checker = ((np.indices((128, 128)).sum(axis=0) // 8) % 2 * 180 + 35).astype(np.uint8)
    sharp = np.repeat(checker[:, :, None], 3, axis=2)
    points = ((40.0, 48.0), (88.0, 48.0), (64.0, 72.0), (48.0, 92.0), (80.0, 92.0))
    fixtures = {
        "sharp-frontal-points": (sharp, points),
        "blurred-frontal-points": (cv.GaussianBlur(sharp, (31, 31), 10), points),
        "tilted-asymmetric-points": (
            sharp,
            ((40.0, 30.0), (88.0, 65.0), (105.0, 75.0), *points[3:]),
        ),
        "missing-points": (sharp, ()),
        "plain-patch": (np.full((128, 128, 3), 90, np.uint8), points),
        "large-pattern": (cv.resize(sharp, (1600, 1600)), points),
    }
    results: dict[str, Any] = {}
    for name, (crop, landmarks) in fixtures.items():
        if name == "large-pattern":
            landmarks = tuple((x * 12.5, y * 12.5) for x, y in landmarks)
        original_size = (float(crop.shape[1]), float(crop.shape[0]))
        timings = []
        for _ in range(50):
            start = time.perf_counter()
            quality = inspect_face_crop(crop, landmarks, (0, 0), original_size)
            timings.append((time.perf_counter() - start) * 1000)
        results[name] = {"samples": 50, "p95_ms": sorted(timings)[47], "diagnostics": quality}
    assert "face-low-detail" in results["blurred-frontal-points"]["diagnostics"]["warnings"]
    assert "face-tilted-eye-line" in results["tilted-asymmetric-points"]["diagnostics"]["warnings"]
    assert "face-geometry-unavailable" in results["missing-points"]["diagnostics"]["warnings"]
    # Compare only the Laplacian stage against full-resolution processing; total
    # bounded-path timing above includes base diagnostics and one shared resample.
    timings = []
    large = fixtures["large-pattern"][0]
    for _ in range(50):
        start = time.perf_counter()
        gray = cv.cvtColor(large, cv.COLOR_BGR2GRAY)
        _detail = float(cv.Laplacian(gray, cv.CV_32F).var())
        timings.append((time.perf_counter() - start) * 1000)
    report = {
        "passed": True,
        "scope": "six generated patterns/point geometries, no actual face or calibrated pose/detail/recognition accuracy",
        "fixtures": results,
        "full_resolution_laplacian_only": {
            "samples": 50,
            "p95_ms": sorted(timings)[47],
            "pixels": 1600 * 1600,
        },
        "bounded_laplacian_pixels": 256 * 256,
    }
    layout = RuntimeLayout()
    layout.configure()
    layout.path("exports/face-quality-benchmark.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
