"""Pinned YuNet on one AI-generated portrait; not biometric calibration."""

import hashlib
import importlib
import json
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

from .capture import CaptureSession
from .media import VideoFrame
from .model_inventory import model_record
from .runtime import RuntimeLayout
from .vision import YuNetProvider


class FixtureFrames:
    def __init__(self, pixels: bytes, width: int, height: int):
        self.pixels, self.width, self.height = pixels, width, height
        self.closed = False

    def frames(self) -> Iterator[VideoFrame]:
        for sequence in range(10):
            if self.closed:
                return
            yield VideoFrame(
                "synthetic-fictional-face",
                sequence,
                time.monotonic(),
                datetime.now(UTC),
                self.width,
                self.height,
                "bgr24",
                self.pixels,
            )

    def close(self) -> None:
        self.closed = True


def main() -> None:
    layout = RuntimeLayout()
    layout.configure()
    root = layout.path("datasets/face-synthetic")
    manifest = json.loads((root / "manifest.json").read_text())
    path = root / manifest["file"]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != manifest["sha256"] or manifest["real_subject"] is not False:
        raise ValueError("pinned synthetic-only face fixture required")
    cv = importlib.import_module("cv2")
    pixels = cv.imread(str(path))
    if pixels is None:
        raise ValueError("synthetic face fixture unavailable")
    height, width = pixels.shape[:2]
    source = FixtureFrames(pixels.tobytes(), width, height)
    provider = YuNetProvider()
    session = CaptureSession(source, None, faces=provider)
    session.state = "running"
    timings = []
    crops = []
    try:
        for frame in source.frames():
            start = time.perf_counter()
            detections = session.faces.detect(frame)
            timings.append((time.perf_counter() - start) * 1000)
            assert len(detections) == 1 and len(detections[0].landmarks) == 5
            updates = session.tracker.update(detections, frame.source_id, frame.sequence)
            session.publish_tracks(updates, time.monotonic())
            session.reference_frame = frame
            session.detections = [d.public_payload() for d in detections]
            assert "landmarks" not in json.dumps(session.snapshot())
            track = UUID(updates[0].track_id)
            before = time.perf_counter()
            jpeg, provenance = session.face_crop(track)
            crops.append((time.perf_counter() - before) * 1000)
            assert jpeg[:2] == b"\xff\xd8"
            quality = provenance["quality"]
            assert quality["face"]["landmarks_available"]
            assert not quality["face"]["calibrated"]
            assert quality["face"]["eye_span_fraction"] > 0
        report = {
            "passed": True,
            "scope": "ten repeats of one AI-generated fictional portrait, pinned real YuNet/track/server-crop path; no real subject, identity or representative quality calibration",
            "fixture_sha256": digest,
            "model_sha256": model_record("yunet")["sha256"],
            "detections_per_frame": 1,
            "detector_p95_ms": max(timings),
            "crop_quality_encode_p95_ms": max(crops),
            "diagnostics": quality,
            "raw_landmarks_not_in_status": True,
        }
    finally:
        session.faces.unload()
        session.tracker.clear()
        session.clear_media()
        source.close()
    assert provider.model is None and not session.face_landmarks and source.closed
    layout.path("exports/face-quality-replay.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
