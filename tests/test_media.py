from datetime import UTC
from pathlib import Path

import pytest
from mnemos.capture import build_capture
from mnemos.media import MicrophoneSource, OpenCVVideoSource, SourceClock, WaveAudioSource
from mnemos.replay import replay


def test_shared_audio_video_replay_clock_and_cleanup(tmp_path):
    cv = pytest.importorskip("cv2")
    numpy = pytest.importorskip("numpy")
    replay(Path("tests/fixtures/scenario.json"), tmp_path)
    video_path = tmp_path / "safe.avi"
    writer = cv.VideoWriter(str(video_path), cv.VideoWriter_fourcc(*"MJPG"), 1, (64, 48))
    assert writer.isOpened()
    for n in range(4):
        writer.write(numpy.full((48, 64, 3), n * 30, dtype=numpy.uint8))
    writer.release()
    clock = SourceClock()
    video = OpenCVVideoSource(video_path, clock=clock)
    frames = list(video.frames())
    audio = WaveAudioSource(tmp_path / "tone.wav", clock=clock)
    chunks = list(audio.chunks())
    assert len(frames) == 4
    assert len(chunks) == 200
    assert frames[0].monotonic_seconds == chunks[0].monotonic_seconds
    assert frames[0].wall_time == chunks[0].wall_time
    assert frames[3].monotonic_seconds - frames[0].monotonic_seconds == 3
    assert sum(len(chunk.samples) for chunk in chunks) == 128000
    assert video.closed and audio.closed
    assert video.capture is None
    with pytest.raises(RuntimeError):
        list(video.frames())


def test_missing_file_fails_and_closes(tmp_path):
    pytest.importorskip("cv2")
    source = OpenCVVideoSource(tmp_path / "missing.avi")
    with pytest.raises(OSError):
        list(source.frames())
    assert source.closed and source.capture is None


def test_native_devices_do_not_start_without_permission():
    with pytest.raises(PermissionError):
        OpenCVVideoSource(0)
    with pytest.raises(PermissionError):
        MicrophoneSource()


def test_build_capture_uses_explicit_camera_index_without_opening_device():
    capture = build_capture("native", True, False, True, False, camera_index=3)
    assert isinstance(capture.video, OpenCVVideoSource)
    assert capture.video.source == 3
    capture.video.close()


def test_camera_candidate_scan_skips_unavailable_index_and_releases_it(monkeypatch):
    cv, np = pytest.importorskip("cv2"), pytest.importorskip("numpy")
    opened = []

    class Driver:
        def __init__(self, index):
            self.index = index
            self.released = False

        def isOpened(self):
            return True

        def set(self, *_args):
            return True

        def get(self, *_args):
            return 30

        def read(self):
            if self.index == 1:
                return True, np.zeros((2, 2, 3), np.uint8)
            return False, None

        def release(self):
            self.released = True

    drivers = {}

    def open_driver(index):
        opened.append(index)
        drivers[index] = Driver(index)
        return drivers[index]

    monkeypatch.setattr(cv, "VideoCapture", open_driver)
    source = OpenCVVideoSource((0, 1, 2, 3, 4), device_authorized=True)
    frames = source.frames()
    first = next(frames)
    frames.close()
    assert opened == [0, 1]
    assert drivers[0].released and drivers[1].released
    assert (first.width, first.height) == (2, 2)
    assert source.closed and source.capture is None


def test_camera_candidate_scan_fails_sanitized_when_none_open(monkeypatch):
    cv = pytest.importorskip("cv2")
    opened = []

    class Driver:
        def isOpened(self):
            return False

        def release(self):
            pass

    monkeypatch.setattr(cv, "VideoCapture", lambda index: opened.append(index) or Driver())
    from mnemos.media import MediaSourceFailure

    with pytest.raises(MediaSourceFailure, match="camera-open-failed"):
        list(OpenCVVideoSource((0, 1, 2), device_authorized=True).frames())
    assert opened == [0, 1, 2]


def test_normalized_media_rejects_unbounded_or_invalid_input():
    from datetime import datetime

    from mnemos.media import AudioChunk, VideoFrame

    at = datetime.now(UTC)
    with pytest.raises(ValueError):
        VideoFrame("source", 0, float("nan"), at, 32, 32, "bgr24", bytes(32 * 32 * 3))
    with pytest.raises(ValueError):
        VideoFrame("source", 0, 1, at, 32000, 32, "bgr24", b"bad")
    with pytest.raises(ValueError):
        AudioChunk("source", 0, 1, at, 16000, 1, "s16le", bytes(64001))
