"""Bounded crop diagnostics; these measurements are not identity confidence."""

import importlib
from typing import Any


def sample_gray(crop: Any) -> Any:
    cv, np = importlib.import_module("cv2"), importlib.import_module("numpy")
    if (
        crop.ndim != 3
        or crop.shape[2] != 3
        or crop.dtype != np.uint8
        or not 32 <= min(crop.shape[:2]) <= max(crop.shape[:2]) <= 4096
    ):
        raise ValueError("bounded BGR uint8 crop at least 32px required")
    height, width = crop.shape[:2]
    scale = min(1.0, 256 / max(height, width))
    sample = (
        cv.resize(
            crop,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv.INTER_AREA,
        )
        if scale < 1
        else crop
    )
    return cv.cvtColor(sample, cv.COLOR_BGR2GRAY)


def describe_gray(gray: Any, width: int, height: int) -> dict[str, Any]:
    np = importlib.import_module("numpy")
    mean, contrast = float(gray.mean()), float(gray.std())
    # Reject only a saturated, essentially featureless frame. A legitimate uniformly
    # colored object is retained with warnings, rather than rejected as unknown.
    if contrast <= 1 and (mean <= 2 or mean >= 253):
        raise ValueError("reference has no usable visual signal; improve light and retry")
    gray_float = gray.astype(np.float32)
    edge = (
        float(np.abs(np.diff(gray_float, axis=0)).mean())
        + float(np.abs(np.diff(gray_float, axis=1)).mean())
    ) / 2
    clipped = float(((gray <= 5) | (gray >= 250)).mean())
    warnings = []
    if contrast < 8:
        warnings.append("low-contrast")
    if edge < 2:
        warnings.append("low-edge-detail")
    if clipped > 0.6:
        warnings.append("clipped-exposure")
    return {
        "version": 1,
        "width": int(width),
        "height": int(height),
        "sample_width": int(gray.shape[1]),
        "sample_height": int(gray.shape[0]),
        "mean_luma": round(mean, 4),
        "contrast_std": round(contrast, 4),
        "edge_mean": round(edge, 4),
        "clipped_fraction": round(clipped, 6),
        "warnings": warnings,
    }


def inspect_crop(crop: Any) -> dict[str, Any]:
    gray = sample_gray(crop)
    height, width = crop.shape[:2]
    return describe_gray(gray, width, height)
