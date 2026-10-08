"""Actual YuNet + Silero + Whisper synthetic replay; no native sensors or identity writes."""

import asyncio
import hashlib
import importlib
import json
import subprocess
import time
import wave
from datetime import UTC, datetime

from .capture import CaptureSession
from .media import SourceClock, VideoFrame, WaveAudioSource
from .metrics import Metrics
from .runtime import RuntimeLayout
from .session_names import SessionNames, introduced_name
from .speech_benchmark import read_pcm
from .speech_stream import StreamingSpeech, TranscriptUpdate
from .vision import Detection, YuNetProvider


class SyntheticPortrait:
    def __init__(self) -> None:
        cv = importlib.import_module("cv2")
        path = RuntimeLayout().path("datasets/face-synthetic/fictional-frontal-v1.png")
        if (
            hashlib.sha256(path.read_bytes()).hexdigest()
            != "f1b4ac96e580c64d5b8bec973a711af0dfd9e38eade50ab5459809a4a7b71a20"
        ):
            raise ValueError("synthetic portrait checksum mismatch")
        image = cv.imread(str(path))
        self.height, self.width = image.shape[:2]
        self.pixels = image.tobytes()
        self.closed = False

    def frames(self):  # type: ignore[no-untyped-def]
        sequence = 0
        while not self.closed:
            yield VideoFrame(
                "synthetic-name-face",
                sequence,
                time.monotonic(),
                datetime.now(UTC),
                self.width,
                self.height,
                "bgr24",
                self.pixels,
            )
            sequence += 1
            time.sleep(0.1)

    def close(self) -> None:
        self.closed = True


class EmptyDetector:
    def detect(self, frame: VideoFrame) -> list[Detection]:
        return []

    def unload(self) -> None:
        pass


def fixture(language: str = "it") -> None:
    layout = RuntimeLayout()
    directory = layout.path("datasets/session-names-synthetic")
    directory.mkdir(parents=True, exist_ok=True)
    temporary = layout.path("tmp/session-names-synthetic.aiff")
    output = directory / ("introduction-" + language + ".wav")
    voice, text = (
        ("Alice", "Questa persona si chiama Maria.")
        if language == "it"
        else ("Samantha", "My name is Alice.")
    )
    subprocess.run(
        ["/usr/bin/say", "-v", voice, "-o", str(temporary), text],
        check=True,
        timeout=30,
    )
    subprocess.run(
        ["/usr/bin/afconvert", "-f", "WAVE", "-d", "LEI16@16000", str(temporary), str(output)],
        check=True,
        timeout=30,
    )
    temporary.unlink()
    with wave.open(str(directory / ("stream-" + language + ".wav")), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(bytes(32000) + read_pcm(output) + bytes(32000 * 6))
    (directory / ("manifest-" + language + ".json")).write_text(
        json.dumps(
            {
                "source": "local macOS synthetic speech; no real speaker",
                "voice": voice,
                "text": text,
                "stream_sha256": hashlib.sha256(
                    (directory / ("stream-" + language + ".wav")).read_bytes()
                ).hexdigest(),
                "redistribution": "not committed; regenerate locally",
            },
            indent=2,
        )
        + "\n"
    )


def build(language: str = "it") -> CaptureSession:
    clock = SourceClock()
    return CaptureSession(
        SyntheticPortrait(),
        WaveAudioSource(
            RuntimeLayout().path("datasets/session-names-synthetic/stream-" + language + ".wav"),
            clock=clock,
        ),
        EmptyDetector(),
        YuNetProvider(),
        speech=StreamingSpeech(language=language),
        clock=clock,
    )


async def replay(language: str = "it") -> dict[str, object]:
    capture = build(language)
    capture.start()
    started = time.perf_counter()
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            status = capture.snapshot()
            named = [track for track in status["tracks"] if track.get("session_name")]
            if named:
                assert len(named) == 1 and named[0]["session_name"]["name"] == (
                    "Maria" if language == "it" else "Alice"
                )
                assert (
                    named[0]["entity_id"] is None
                    and named[0]["session_name"]["verified_identity"] is False
                )
                return {
                    "passed": True,
                    "scope": "one generated fictional face and synthetic introduction; not identity accuracy",
                    "language": language,
                    "time_to_name_ms": round((time.perf_counter() - started) * 1000, 3),
                    "audio_chunks": status["audio_chunks"],
                    "processed_frames": status["processed_frames"],
                    "cloud_calls": 0,
                    "catalog_writes": 0,
                }
            if status["state"] == "failed":
                raise RuntimeError("synthetic replay failed")
            await asyncio.sleep(0.05)
        raise RuntimeError("no automatic name from actual local speech replay")
    finally:
        await capture.stop()
        assert capture.snapshot()["tracks"] == [] and capture.snapshot()["transcripts"] == []


def benchmark() -> dict[str, object]:
    metrics = Metrics()
    cases = [
        ("Mi chiamo Andrea.", "Andrea"),
        ("My name is Alice", "Alice"),
        ("Non mi chiamo Andrea", None),
        ("Mi chiamo Andrea e poi paga", None),
    ]
    names = SessionNames()
    at = time.monotonic()
    tracks = {"synthetic-face": {"label": "face"}}
    names.observe(tracks, at - 1)
    names.observe(tracks, at)
    for i in range(1000):
        text, expected = cases[i % len(cases)]
        with metrics.measure("grammar"):
            assert introduced_name(text) == expected
        update = TranscriptUpdate(
            str(i), "synthetic", at - 0.5, at, text, "en", 0.99, False, "anonymous"
        )
        with metrics.measure("offer"):
            names.offer(update, tracks, at)
    assert len(names.seen) == 200 and len(names.labels) <= 1
    return {
        "passed": True,
        "scope": "synthetic narrow grammar and bounded annotation cost",
        "metrics": metrics.report(),
        "dedup_max": 200,
    }


def main() -> None:
    for language in ("it", "en"):
        fixture(language)
    report = {
        "replay_it": asyncio.run(replay("it")),
        "replay_en": asyncio.run(replay("en")),
        "benchmark": benchmark(),
    }
    RuntimeLayout().path("exports/session-names-replay.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
