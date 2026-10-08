import importlib
import math
import os
import time
from datetime import UTC, datetime
from uuid import UUID

import pytest
from mnemos.capture import CaptureSession
from mnemos.face_quality import inspect_face_crop
from mnemos.media import VideoFrame
from mnemos.tracking import TrackUpdate
from mnemos.vision import Box, Detection, YuNetProvider

POINTS = ((40.0, 48.0), (88.0, 48.0), (64.0, 72.0), (48.0, 92.0), (80.0, 92.0))


def patterned():
    np = importlib.import_module("numpy")
    checker = ((np.indices((128, 128)).sum(axis=0) // 8) % 2 * 180 + 35).astype(np.uint8)
    return np.repeat(checker[:, :, None], 3, axis=2)


def test_generated_detail_and_geometry_are_diagnostics_only():
    cv = importlib.import_module("cv2")
    sharp = inspect_face_crop(patterned(), POINTS, (0, 0), (128, 128))
    blurry = inspect_face_crop(
        cv.GaussianBlur(patterned(), (31, 31), 10), POINTS, (0, 0), (128, 128)
    )
    assert sharp["face"]["laplacian_variance"] > blurry["face"]["laplacian_variance"]
    assert "face-low-detail" in blurry["warnings"]
    assert not sharp["face"]["calibrated"]
    assert sharp["face"]["eye_line_roll_degrees"] == 0
    assert sharp["face"]["nose_eye_axis_offset"] == 0
    assert "landmarks" not in sharp["face"]
    changed = ((40.0, 30.0), (88.0, 65.0), (105.0, 75.0), *POINTS[3:])
    turned = inspect_face_crop(patterned(), changed, (0, 0), (128, 128))
    assert "face-tilted-eye-line" in turned["warnings"]
    assert "face-asymmetric-proxy" in turned["warnings"]
    swapped = inspect_face_crop(
        patterned(), (POINTS[1], POINTS[0], *POINTS[2:]), (0, 0), (128, 128)
    )
    assert swapped["face"] == sharp["face"]


def test_unavailable_degenerate_invalid_and_crop_relative_geometry():
    missing = inspect_face_crop(patterned(), (), (16, 16), (96, 96))
    assert "face-geometry-unavailable" in missing["warnings"]
    assert "eye_line_roll_degrees" not in missing["face"]
    same = inspect_face_crop(patterned(), (POINTS[0], POINTS[0], *POINTS[2:]), (0, 0), (128, 128))
    assert "face-degenerate-geometry" in same["warnings"]
    outside = inspect_face_crop(patterned(), POINTS, (50, 50), (96, 96))
    assert "face-landmarks-outside-crop" in outside["warnings"]
    for invalid in (POINTS[:4], ((math.nan, 48), *POINTS[1:]), ((math.inf, 48), *POINTS[1:])):
        with pytest.raises(ValueError):
            inspect_face_crop(patterned(), invalid, (0, 0), (128, 128))
    for origin, size in (((math.nan, 0), (128, 128)), ((0, 0), (0, 128))):
        with pytest.raises(ValueError):
            inspect_face_crop(patterned(), POINTS, origin, size)
    translated = tuple((x + 100, y + 200) for x, y in POINTS)
    large = inspect_face_crop(patterned(), translated, (100, 200), (128, 128))
    assert large["face"]["eye_line_roll_degrees"] == 0
    assert "face-landmarks-outside-crop" not in large["warnings"]


def test_yunet_output_landmarks_finite_schema_and_public_redaction():
    np = importlib.import_module("numpy")

    class Model:
        rows = np.array(
            [[16, 16, 96, 96, *(v for point in POINTS for v in point), 0.9]], dtype=np.float32
        )

        def setInputSize(self, size):
            pass

        def detect(self, pixels):
            return None, self.rows

    provider = YuNetProvider()
    provider.model = model = Model()
    frame = VideoFrame(
        "synthetic",
        1,
        time.monotonic(),
        datetime.now(UTC),
        128,
        128,
        "bgr24",
        patterned().tobytes(),
    )
    (detection,) = provider.detect(frame)
    assert detection.landmarks == POINTS
    assert "landmarks" not in detection.public_payload()
    model.rows[0, 4] = np.nan
    assert provider.detect(frame) == []
    model.rows = np.zeros((1, 14), dtype=np.float32)
    with pytest.raises(ValueError, match="schema"):
        provider.detect(frame)
    provider.unload()


def test_capture_geometry_private_fresh_and_stop_cleared():
    session = CaptureSession(object(), None)
    session.state = "running"
    frame = VideoFrame(
        "synthetic",
        1,
        time.monotonic(),
        datetime.now(UTC),
        128,
        128,
        "bgr24",
        patterned().tobytes(),
    )
    detection = Detection("face", 0.9, Box(16, 16, 96, 96), frame.source_id, frame.sequence, POINTS)
    updates = session.tracker.update([detection], frame.source_id, frame.sequence)
    session.publish_tracks(updates, frame.monotonic_seconds)
    session.reference_frame = frame
    session.detections = [detection.public_payload()]
    track = UUID(updates[0].track_id)
    assert "landmarks" not in session.snapshot()["tracks"][0]
    _, provenance = session.face_crop(track)
    assert provenance["quality"]["face"]["landmarks_available"]
    assert "landmarks" not in provenance
    session.publish_tracks([], time.monotonic())
    assert session.face_landmarks == {}
    with pytest.raises(KeyError):
        session.face_crop(track)
    session.publish_tracks([TrackUpdate("update", str(track), detection)], time.monotonic())
    session.fail("synthetic failure")
    assert not session.face_landmarks and not session.visible_tracks


@pytest.mark.skipif(
    not os.environ.get("MNEMOS_TEST_MODELS"), reason="real YuNet synthetic portrait replay opt-in"
)
def test_real_yunet_synthetic_portrait_quality_replay():
    from mnemos.face_quality_replay import main

    main()
