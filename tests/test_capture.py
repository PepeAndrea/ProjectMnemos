import asyncio
import os
import time
from datetime import UTC, datetime

import pytest
from mnemos.capture import CaptureSession, build_capture
from mnemos.media import AudioChunk, VideoFrame


class FakeSource:
    def __init__(self, fail=False):
        self.closed = False
        self.fail = fail

    def frames(self):
        if self.fail:
            raise OSError("test disconnect")
        for n in range(20):
            yield VideoFrame(
                "test", n, time.monotonic(), datetime.now(UTC), 32, 32, "bgr24", bytes(32 * 32 * 3)
            )

    def chunks(self):
        for n in range(20):
            yield AudioChunk(
                "test", n, time.monotonic(), datetime.now(UTC), 16000, 1, "s16le", bytes(640)
            )

    def close(self):
        self.closed = True


class FakeDetector:
    def __init__(self):
        self.unloaded = False

    def detect(self, frame):
        time.sleep(0.01)
        return []

    def unload(self):
        self.unloaded = True


def test_ingest_backpressure_stop_and_privacy_cleanup():
    async def run():
        video, audio = FakeSource(), FakeSource()
        detector, face = FakeDetector(), FakeDetector()
        capture = CaptureSession(video, audio, detector, face)
        capture.start()
        await capture.task
        snapshot = capture.snapshot()
        assert snapshot["state"] == "completed"
        assert snapshot["video_frames"] == snapshot["audio_chunks"] == 20
        assert snapshot["queue_depth"] == 0 and snapshot["drops"] > 0
        assert snapshot["audio_buffer_bytes"] == snapshot["video_buffer_bytes"] == 0
        assert capture.jpeg is None and video.closed and audio.closed
        assert detector.unloaded and face.unloaded
        await capture.stop()
        assert capture.state == "stopped"

    asyncio.run(run())


def test_disconnect_fails_visibly_and_releases_source():
    async def run():
        source = FakeSource(fail=True)
        capture = CaptureSession(source, None, FakeDetector(), FakeDetector())
        capture.start()
        await capture.task
        assert capture.state == "failed" and source.closed
        assert capture.snapshot()["error"] == "video source or normalization failed"

    asyncio.run(run())


def test_native_capture_requires_independent_consent():
    with pytest.raises(PermissionError):
        build_capture("native", True, False, False, False)
    with pytest.raises(PermissionError):
        build_capture("native", False, True, False, False)


def test_missing_media_dependency_fails_closed_and_closes_source(monkeypatch):
    import mnemos.capture as module

    real_import = module.importlib.import_module

    def missing(name):
        if name == "cv2":
            raise ImportError("media extra unavailable")
        return real_import(name)

    monkeypatch.setattr(module.importlib, "import_module", missing)

    async def run():
        source = FakeSource()
        capture = CaptureSession(source, None, FakeDetector(), FakeDetector())
        capture.start()
        await capture.task
        assert capture.state == "failed" and source.closed
        assert capture.snapshot()["queue_depth"] == 0

    asyncio.run(run())


@pytest.mark.skipif(
    not os.environ.get("MNEMOS_TEST_MODELS"), reason="real stream integration opt-in"
)
def test_real_replay_stream_preview_and_stop_cleanup():
    async def run():
        capture = build_capture("replay", True, True, False, False)
        capture.start()
        deadline = time.monotonic() + 5
        while capture.jpeg is None and time.monotonic() < deadline:
            await asyncio.sleep(0.02)
        assert capture.jpeg is not None, capture.snapshot()
        before = capture.snapshot()
        assert before["state"] == "running" and before["detections"]
        assert before["queue_depth"] <= 2
        start = time.monotonic()
        await capture.stop()
        assert time.monotonic() - start < 5
        after = capture.snapshot()
        assert after["state"] == "stopped"
        assert after["audio_buffer_bytes"] == after["video_buffer_bytes"] == 0
        assert after["queue_depth"] == 0 and capture.jpeg is None
        assert capture.detector.model is None and capture.faces.model is None

    asyncio.run(run())


class FakeSpeech:
    def __init__(self, fail=False):
        self.fail = fail
        self.discontinuities = 0
        self.closed = self.cancelled = self.flushed = False

    def prepare(self):
        if self.fail:
            raise OSError("missing speech weights")

    def feed(self, chunk):
        from mnemos.speech_stream import TranscriptUpdate

        time.sleep(0.01)
        return [
            TranscriptUpdate(
                "same-revision",
                chunk.source_id,
                chunk.monotonic_seconds,
                chunk.monotonic_seconds + 0.02,
                "synthetic text",
                "en",
                0.8,
                True,
                "anonymous-test",
            )
        ]

    def flush(self):
        self.flushed = True
        return []

    def cancel(self):
        self.cancelled = True

    def close(self):
        self.closed = True


def test_speech_startup_failure_never_opens_source_and_clears_media():
    async def run():
        source, speech = FakeSource(), FakeSpeech(fail=True)
        capture = CaptureSession(None, source, speech=speech)
        capture.start()
        await capture.task
        assert capture.state == "failed" and source.closed and speech.closed
        assert capture.snapshot()["audio_chunks"] == 0
        assert capture.snapshot()["transcripts"] == []

    asyncio.run(run())


def test_audio_queue_backpressure_and_stop_retract_transcript():
    class Burst(FakeSource):
        def chunks(self):
            for n in range(500):
                yield AudioChunk(
                    "burst", n, time.monotonic(), datetime.now(UTC), 16000, 1, "s16le", bytes(640)
                )

    async def run():
        speech = FakeSpeech()
        capture = CaptureSession(None, Burst(), speech=speech)
        capture.start()
        for _ in range(100):
            if capture.snapshot()["transcripts"]:
                break
            await asyncio.sleep(0.01)
        before = capture.snapshot()
        assert before["transcripts"] and before["audio_drops"] > 0
        assert before["audio_queue_depth"] <= 128
        assert len(before["transcripts"]) == 1
        await capture.stop()
        after = capture.snapshot()
        assert after["state"] == "stopped" and after["transcripts"] == []
        assert after["audio_queue_depth"] == after["audio_buffer_bytes"] == 0
        assert speech.cancelled and speech.closed

    asyncio.run(run())


@pytest.mark.skipif(not os.environ.get("MNEMOS_TEST_SPEECH"), reason="real speech capture opt-in")
def test_real_paced_capture_exposes_transcript_then_stop_clears_it():
    async def run():
        capture = build_capture(
            "speech-replay", False, True, False, False, transcribe=True, language="en"
        )
        capture.start()
        deadline = time.monotonic() + 15
        while not capture.snapshot()["transcripts"] and time.monotonic() < deadline:
            await asyncio.sleep(0.02)
        before = capture.snapshot()
        assert before["state"] == "running" and before["transcripts"], before
        assert before["audio_queue_depth"] <= 128
        assert all(
            item["speaker_session_id"].startswith("anonymous-") for item in before["transcripts"]
        )
        await capture.stop()
        after = capture.snapshot()
        assert after["state"] == "stopped" and not after["transcripts"]
        assert after["transcribing"] is False
        assert after["audio_buffer_bytes"] == after["audio_queue_depth"] == 0
        assert capture.speech.asr.context is None

    asyncio.run(run())


def test_audio_eof_flushes_speech_without_waiting_for_video_eof():
    class LongerVideo(FakeSource):
        def frames(self):
            origin = time.monotonic()
            for n in range(2):
                yield VideoFrame(
                    "video",
                    n,
                    origin + n * 5,
                    datetime.now(UTC),
                    32,
                    32,
                    "bgr24",
                    bytes(32 * 32 * 3),
                )

    async def run():
        speech = FakeSpeech()
        capture = CaptureSession(
            LongerVideo(), FakeSource(), FakeDetector(), FakeDetector(), speech=speech
        )
        capture.start()
        for _ in range(100):
            if speech.flushed:
                break
            await asyncio.sleep(0.01)
        assert speech.flushed and speech.closed
        assert capture.snapshot()["state"] == "running"
        assert capture.snapshot()["audio_ended"] is True
        assert capture.snapshot()["video_ended"] is False
        assert capture.snapshot()["transcribing"] is False
        await capture.stop()
        assert capture.state == "stopped"

    asyncio.run(run())
