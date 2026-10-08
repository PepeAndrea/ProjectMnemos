import asyncio
import importlib
import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from mnemos.capture import CaptureSession
from mnemos.media import MediaFailureCode, MediaSourceFailure, MicrophoneSource, OpenCVVideoSource

SECRET = "private-device-name/private-file-path"


@pytest.mark.parametrize("file", [False, True])
def test_video_open_failure_is_sanitized_and_closed(monkeypatch, file):
    cv = importlib.import_module("cv2")

    class Driver:
        released = False
        reads = 0

        def isOpened(self):
            return False

        def release(self):
            self.released = True

    driver = Driver()
    monkeypatch.setattr(cv, "VideoCapture", lambda *args: driver)
    source = OpenCVVideoSource(Path(SECRET) if file else 0, device_authorized=not file)
    with pytest.raises(MediaSourceFailure) as caught:
        list(source.frames())
    assert caught.value.code == ("video-file-unavailable" if file else "camera-open-failed")
    assert SECRET not in str(caught.value)
    assert source.closed and driver.released and source.capture is None


@pytest.mark.parametrize(
    "fault,code",
    [
        ("constructor", "camera-open-failed"),
        ("configuration", "camera-open-failed"),
        ("read", "camera-stream-ended"),
        ("bad-frame", "video-frame-invalid"),
    ],
)
def test_camera_stage_failure_and_resource_release(monkeypatch, fault, code):
    cv, np = importlib.import_module("cv2"), importlib.import_module("numpy")

    class Driver:
        released = False
        reads = 0

        def isOpened(self):
            return True

        def set(self, *args):
            if fault == "configuration":
                raise OSError(SECRET)

        def get(self, *args):
            return 30

        def read(self):
            self.reads += 1
            if fault == "read" and self.reads > 1:
                raise OSError(SECRET)
            return True, np.zeros((32, 32, 4) if fault != "read" else (32, 32, 3), np.uint8)

        def release(self):
            self.released = True

    driver = Driver()

    def open_driver(*args):
        if fault == "constructor":
            raise OSError(SECRET)
        return driver

    monkeypatch.setattr(cv, "VideoCapture", open_driver)
    source = OpenCVVideoSource(0, device_authorized=True)
    with pytest.raises(MediaSourceFailure) as caught:
        list(source.frames())
    assert caught.value.code == code and SECRET not in str(caught.value)
    assert source.closed and source.capture is None
    assert driver.released or fault == "constructor"


def test_video_empty_vs_normal_eof_and_invalid_fps_fallback(monkeypatch, tmp_path):
    cv, np = importlib.import_module("cv2"), importlib.import_module("numpy")

    class Driver:
        index = 0
        capacity = 0

        def isOpened(self):
            return True

        def get(self, *args):
            return float("nan")

        def read(self):
            self.index += 1
            return self.index <= self.capacity, np.zeros((32, 32, 3), np.uint8)

        def release(self):
            pass

    driver = Driver()
    monkeypatch.setattr(cv, "VideoCapture", lambda *args: driver)
    with pytest.raises(MediaSourceFailure, match="video-file-unreadable"):
        list(OpenCVVideoSource(tmp_path / "fixture", fps=10).frames())
    driver.index, driver.capacity = 0, 2
    frames = list(OpenCVVideoSource(tmp_path / "fixture", fps=10).frames())
    assert len(frames) == 2 and frames[1].monotonic_seconds - frames[
        0
    ].monotonic_seconds == pytest.approx(0.1)


@pytest.mark.parametrize("stage", ["constructor", "enter", "read"])
def test_microphone_stage_failure_sanitized_and_closed(monkeypatch, stage):
    import mnemos.media as module

    class Stream:
        closed = False

        def __enter__(self):
            if stage == "enter":
                raise OSError(SECRET)
            return self

        def __exit__(self, *args):
            pass

        def read(self, *args):
            raise OSError(SECRET)

        def close(self):
            self.closed = True

    stream = Stream()

    def open_stream(**kwargs):
        if stage == "constructor":
            raise OSError(SECRET)
        return stream

    actual_import = module.importlib.import_module
    monkeypatch.setattr(
        module.importlib,
        "import_module",
        lambda name: (
            SimpleNamespace(RawInputStream=open_stream)
            if name == "sounddevice"
            else actual_import(name)
        ),
    )
    source = MicrophoneSource(device_authorized=True)
    with pytest.raises(MediaSourceFailure) as caught:
        list(source.chunks())
    assert caught.value.code == (
        "microphone-read-failed" if stage == "read" else "microphone-open-failed"
    )
    assert SECRET not in str(caught.value) and source.closed and source.stream is None
    assert stream.closed or stage == "constructor"


def test_failed_worker_state_first_cause_and_explicit_restart():
    gate = threading.Event()

    class Failing:
        closed = False

        def frames(self):
            raise MediaSourceFailure(MediaFailureCode.CAMERA_OPEN)
            yield

        def close(self):
            self.closed = True
            if not gate.wait(2):
                raise TimeoutError("fixture close gate")

    class Detector:
        def detect(self, frame):
            return []

        def unload(self):
            pass

    async def run():
        source = Failing()
        capture = CaptureSession(source, None, Detector(), Detector())
        capture.start()
        until = time.monotonic() + 1
        while capture.error_code is None and time.monotonic() < until:
            await asyncio.sleep(0.01)
        state = capture.snapshot()
        assert state["state"] == "failed" and state["worker_active"]
        assert state["error_code"] == "camera-open-failed" and SECRET not in json.dumps(state)
        assert not state["tracks"] and not state["transcripts"] and not state["video_buffer_bytes"]
        capture.fail("secondary cleanup error")
        assert capture.error_code == "camera-open-failed"
        gate.set()
        await capture.task
        assert not capture.snapshot()["worker_active"]
        await capture.stop()
        assert capture.state == "stopped"
        fresh = CaptureSession(Failing(), None, Detector(), Detector())
        assert fresh.snapshot()["error_code"] is None and fresh.error is None

    try:
        asyncio.run(run())
    finally:
        gate.set()


def test_release_failure_does_not_hide_primary_error_or_retain_handle(monkeypatch):
    cv = importlib.import_module("cv2")

    class Driver:
        def isOpened(self):
            return False

        def release(self):
            raise OSError(SECRET)

    monkeypatch.setattr(cv, "VideoCapture", lambda *args: Driver())
    source = OpenCVVideoSource(0, device_authorized=True)
    with pytest.raises(MediaSourceFailure) as caught:
        list(source.frames())
    assert caught.value.code == "camera-open-failed" and source.cleanup_failed
    assert source.closed and source.capture is None
    source.close()  # idempotent, no second release on a detached handle


def test_stop_during_read_error_is_a_clean_stop():
    gate = threading.Event()

    class Source:
        closed = False

        def frames(self):
            assert gate.wait(2)
            raise MediaSourceFailure(MediaFailureCode.CAMERA_READ)
            yield

        def close(self):
            self.closed = True

    class Detector:
        def detect(self, frame):
            return []

        def unload(self):
            pass

    async def run():
        source = Source()
        capture = CaptureSession(source, None, Detector(), Detector())
        capture.start()
        await asyncio.sleep(0.01)
        stopping = asyncio.create_task(capture.stop())
        await asyncio.sleep(0.01)
        gate.set()
        await stopping
        assert capture.state == "stopped" and capture.error is None and capture.error_code is None
        assert source.closed and not capture.snapshot()["worker_active"]

    try:
        asyncio.run(run())
    finally:
        gate.set()
