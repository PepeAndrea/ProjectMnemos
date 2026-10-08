"""Local acquisition diagnostics, never calibrated pose or biometric identity."""

import importlib
import math
from typing import Any

from .reference_quality import describe_gray, sample_gray


def inspect_face_crop(
    crop: Any,
    landmarks: tuple[tuple[float, float], ...],
    origin: tuple[float, float],
    original_size: tuple[float, float],
) -> dict[str, Any]:
    gray = sample_gray(crop)
    height, width = crop.shape[:2]
    quality = describe_gray(gray, width, height)
    cv = importlib.import_module("cv2")
    detail = float(cv.Laplacian(gray, cv.CV_32F).var())
    diagnostics: dict[str, Any] = {
        "version": 1,
        "method": "bounded-laplacian-and-five-point-geometry",
        "laplacian_variance": round(detail, 4),
        "landmarks_available": bool(landmarks),
        "calibrated": False,
    }
    warnings = quality["warnings"]
    if detail < 25:
        warnings.append("face-low-detail")
    if not landmarks:
        warnings.append("face-geometry-unavailable")
    else:
        if len(landmarks) != 5 or any(
            len(point) != 2 or not all(math.isfinite(value) for value in point)
            for point in landmarks
        ):
            raise ValueError("five finite face landmarks required")
        original_width, original_height = original_size
        if (
            not all(math.isfinite(value) for value in (*origin, *original_size))
            or min(original_size) <= 0
        ):
            raise ValueError("finite positive original face geometry required")
        if any(
            not origin[0] <= x <= origin[0] + original_width
            or not origin[1] <= y <= origin[1] + original_height
            for x, y in landmarks
        ):
            warnings.append("face-landmarks-outside-crop")
        # Sort eyes by screen position: roll remains invariant to provider eye ordering.
        left, right = sorted(landmarks[:2])
        dx, dy = right[0] - left[0], right[1] - left[1]
        span = math.hypot(dx, dy)
        if span <= 1:
            warnings.append("face-degenerate-geometry")
        else:
            roll = math.degrees(math.atan2(dy, dx))
            midpoint = ((left[0] + right[0]) / 2, (left[1] + right[1]) / 2)
            nose = landmarks[2]
            offset = ((nose[0] - midpoint[0]) * dx + (nose[1] - midpoint[1]) * dy) / span**2
            diagnostics.update(
                {
                    "eye_line_roll_degrees": round(roll, 4),
                    "eye_span_fraction": round(span / original_width, 6),
                    "nose_eye_axis_offset": round(offset, 6),
                }
            )
            if abs(roll) > 20:
                warnings.append("face-tilted-eye-line")
            if span / original_width < 0.15:
                warnings.append("face-small-eye-span")
            if abs(offset) > 0.35:
                warnings.append("face-asymmetric-proxy")
    quality["face"] = diagnostics
    return quality
