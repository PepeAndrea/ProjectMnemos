"""Common normalized native/file media contracts, without automatic recording."""

import importlib
import math
import time
import wave
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol


class MediaFailureCode(StrEnum):
    CAMERA_OPEN = "camera-open-failed"
    CAMERA_READ = "camera-stream-ended"
    VIDEO_OPEN = "video-file-unavailable"
    VIDEO_READ = "video-file-unreadable"
    VIDEO_FORMAT = "video-frame-invalid"
    MICROPHONE_OPEN = "microphone-open-failed"
    MICROPHONE_READ = "microphone-read-failed"
    VIDEO_CLOSE = "video-close-failed"
    MICROPHONE_CLOSE = "microphone-close-failed"


class MediaSourceFailure(OSError):
    """Finite public codes: never expose device names, paths or driver exception text."""

    def __init__(self, code: MediaFailureCode):
        self.code = code.value
        super().__init__(code.value)


@dataclass(frozen=True)
class VideoFrame:
    source_id: str
    sequence: int
    monotonic_seconds: float
    wall_time: datetime
    width: int
    height: int
    pixel_format: str
    pixels: bytes

    def __post_init__(self) -> None:
        if (
            not self.source_id
            or len(self.source_id) > 128
            or self.sequence < 0
            or not math.isfinite(self.monotonic_seconds)
            or self.monotonic_seconds < 0
            or self.wall_time.tzinfo is None
            or not 0 < self.width <= 4096
            or not 0 < self.height <= 4096
            or self.pixel_format not in {"bgr24", "rgb24"}
            or len(self.pixels) != self.width * self.height * 3
        ):
            raise ValueError("invalid normalized video frame")


@dataclass(frozen=True)
class AudioChunk:
    source_id: str
    sequence: int
    monotonic_seconds: float
    wall_time: datetime
    sample_rate: int
    channels: int
    sample_format: str
    samples: bytes

    def __post_init__(self) -> None:
        if (
            not self.source_id
            or len(self.source_id) > 128
            or self.sequence < 0
            or not math.isfinite(self.monotonic_seconds)
            or self.monotonic_seconds < 0
            or self.wall_time.tzinfo is None
            or not 8000 <= self.sample_rate <= 48000
            or self.channels not in {1, 2}
            or self.sample_format != "s16le"
            or not self.samples
            or len(self.samples) > self.sample_rate * self.channels * 2
            or len(self.samples) % (self.channels * 2)
        ):
            raise ValueError("invalid normalized audio chunk")


class VideoSource(Protocol):
    def frames(self) -> Iterator[VideoFrame]: ...
    def close(self) -> None: ...


class AudioSource(Protocol):
    def chunks(self) -> Iterator[AudioChunk]: ...
    def close(self) -> None: ...


class SourceClock:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.origin = time.monotonic()
        self.wall_origin = datetime.now(UTC)

    def wall_at(self, seconds: float) -> datetime:
        return self.wall_origin + timedelta(seconds=seconds - self.origin)


class OpenCVVideoSource:
    """Open only on explicit frames(); accepts native camera or replay file."""

    def __init__(
        self,
        source: int | tuple[int, ...] | Path,
        source_id: str = "local-video",
        *,
        width: int = 1280,
        height: int = 720,
        fps: float = 30,
        clock: SourceClock | None = None,
        device_authorized: bool = False,
    ):
        if width < 1 or height < 1 or not 0 < fps <= 60:
            raise ValueError("invalid video configuration")
        if isinstance(source, int) and not device_authorized:
            raise PermissionError("explicit camera permission required")
        if isinstance(source, tuple) and (
            not source
            or any(not isinstance(index, int) or index < 0 for index in source)
            or len(set(source)) != len(source)
        ):
            raise ValueError("invalid camera candidates")
        if isinstance(source, tuple) and not device_authorized:
            raise PermissionError("explicit camera permission required")
        self.source = source
        self.source_id = source_id
        self.width, self.height, self.fps = width, height, fps
        self.clock = clock or SourceClock()
        self.capture: Any = None
        self.closed = False
        self.cleanup_failed = False

    def frames(self) -> Iterator[VideoFrame]:
        if self.closed:
            raise RuntimeError("source closed")
        cv = importlib.import_module("cv2")
        is_file = isinstance(self.source, Path)
        sequence = 0
        initial_frame: Any = None
        failure: MediaSourceFailure | None = None
        try:
            try:
                candidates = (
                    (str(self.source),)
                    if is_file
                    else (self.source if isinstance(self.source, tuple) else (self.source,))
                )
                for candidate in candidates:
                    handle = None
                    try:
                        handle = cv.VideoCapture(candidate)
                        if not handle.isOpened():
                            handle.release()
                            continue
                        if not is_file:
                            handle.set(cv.CAP_PROP_FRAME_WIDTH, self.width)
                            handle.set(cv.CAP_PROP_FRAME_HEIGHT, self.height)
                            handle.set(cv.CAP_PROP_FPS, self.fps)
                            ok, initial_frame = handle.read()
                            if not ok:
                                handle.release()
                                initial_frame = None
                                continue
                        self.capture = handle
                        break
                    except Exception:  # noqa: BLE001 - move to the next authorized candidate
                        if handle is not None:
                            try:
                                handle.release()
                            except Exception:  # noqa: BLE001 - sanitized below
                                self.cleanup_failed = True
                        continue
                if self.capture is None:
                    raise OSError("no camera candidate opened")
                source_fps = float(self.capture.get(cv.CAP_PROP_FPS))
                if not math.isfinite(source_fps) or source_fps <= 0:
                    source_fps = self.fps
            except Exception:  # noqa: BLE001 - sanitize driver errors at the source boundary
                raise MediaSourceFailure(
                    MediaFailureCode.VIDEO_OPEN if is_file else MediaFailureCode.CAMERA_OPEN
                ) from None
            while not self.closed:
                try:
                    if initial_frame is not None:
                        frame, initial_frame = initial_frame, None
                        ok = True
                    else:
                        ok, frame = self.capture.read()
                except Exception:  # noqa: BLE001 - no driver/path text in public diagnostics
                    if self.closed:
                        break
                    raise MediaSourceFailure(
                        MediaFailureCode.VIDEO_READ if is_file else MediaFailureCode.CAMERA_READ
                    ) from None
                if not ok:
                    if not is_file:
                        raise MediaSourceFailure(MediaFailureCode.CAMERA_READ)
                    if sequence == 0:
                        raise MediaSourceFailure(MediaFailureCode.VIDEO_READ)
                    break
                if (
                    frame is None
                    or frame.ndim != 3
                    or frame.shape[2] != 3
                    or str(frame.dtype) != "uint8"
                    or not 0 < frame.shape[0] <= 4096
                    or not 0 < frame.shape[1] <= 4096
                ):
                    raise MediaSourceFailure(MediaFailureCode.VIDEO_FORMAT)
                seconds = self.clock.origin + sequence / source_fps if is_file else time.monotonic()
                height, width = frame.shape[:2]
                yield VideoFrame(
                    self.source_id,
                    sequence,
                    seconds,
                    self.clock.wall_at(seconds),
                    width,
                    height,
                    "bgr24",
                    frame.tobytes(),
                )
                sequence += 1
        except MediaSourceFailure as exc:
            failure = exc
            raise
        finally:
            try:
                self.close()
            except MediaSourceFailure:
                if failure is None:
                    raise

    def close(self) -> None:
        self.closed = True
        capture, self.capture = self.capture, None
        if capture is not None:
            try:
                capture.release()
            except Exception:  # noqa: BLE001 - sanitize release failures, retain failure flag
                self.cleanup_failed = True
                raise MediaSourceFailure(MediaFailureCode.VIDEO_CLOSE) from None


class WaveAudioSource:
    def __init__(
        self,
        path: Path,
        source_id: str = "replay-audio",
        *,
        chunk_ms: int = 20,
        clock: SourceClock | None = None,
    ):
        if not 1 <= chunk_ms <= 1000:
            raise ValueError("invalid audio chunk duration")
        self.path, self.source_id, self.chunk_ms = path, source_id, chunk_ms
        self.clock = clock or SourceClock()
        self.closed = False

    def chunks(self) -> Iterator[AudioChunk]:
        if self.closed:
            raise RuntimeError("source closed")
        try:
            with wave.open(str(self.path), "rb") as stream:
                if stream.getsampwidth() != 2:
                    raise ValueError("16-bit PCM required")
                rate, channels = stream.getframerate(), stream.getnchannels()
                count = max(1, int(rate * self.chunk_ms / 1000))
                sample_offset = 0
                sequence = 0
                while not self.closed:
                    samples = stream.readframes(count)
                    if not samples:
                        break
                    seconds = self.clock.origin + sample_offset / rate
                    yield AudioChunk(
                        self.source_id,
                        sequence,
                        seconds,
                        self.clock.wall_at(seconds),
                        rate,
                        channels,
                        "s16le",
                        samples,
                    )
                    sample_offset += len(samples) // (channels * 2)
                    sequence += 1
        finally:
            self.close()

    def close(self) -> None:
        self.closed = True


class MicrophoneSource:
    """Blocking chunk reader; run in a dedicated ingestion thread, never the API loop."""

    def __init__(
        self,
        device: int | None = None,
        source_id: str = "local-mic",
        *,
        sample_rate: int = 16000,
        chunk_ms: int = 20,
        clock: SourceClock | None = None,
        device_authorized: bool = False,
    ):
        if not device_authorized:
            raise PermissionError("explicit microphone permission required")
        if not 8000 <= sample_rate <= 48000 or not 1 <= chunk_ms <= 100:
            raise ValueError("invalid audio configuration")
        self.device, self.source_id = device, source_id
        self.sample_rate = sample_rate
        self.blocksize = int(sample_rate * chunk_ms / 1000)
        self.clock = clock or SourceClock()
        self.closed = False
        self.cleanup_failed = False
        self.overflows = 0
        self.stream: Any = None

    def chunks(self) -> Iterator[AudioChunk]:
        if self.closed:
            raise RuntimeError("source closed")
        sd = importlib.import_module("sounddevice")
        stage = MediaFailureCode.MICROPHONE_OPEN
        failure: MediaSourceFailure | None = None
        try:
            self.stream = sd.RawInputStream(
                device=self.device,
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=self.blocksize,
            )
            with self.stream:
                stage = MediaFailureCode.MICROPHONE_READ
                sequence = 0
                while not self.closed:
                    samples, overflow = self.stream.read(self.blocksize)
                    self.overflows += int(overflow)
                    seconds = time.monotonic() - self.blocksize / self.sample_rate
                    yield AudioChunk(
                        self.source_id,
                        sequence,
                        seconds,
                        self.clock.wall_at(seconds),
                        self.sample_rate,
                        1,
                        "s16le",
                        bytes(samples),
                    )
                    sequence += 1
        except Exception:  # noqa: BLE001 - microphone driver messages can contain private details
            if not self.closed:
                failure = MediaSourceFailure(stage)
                raise failure from None
        finally:
            try:
                self.close()
            except MediaSourceFailure:
                if failure is None:
                    raise

    def close(self) -> None:
        self.closed = True
        stream, self.stream = self.stream, None
        if stream is not None:
            try:
                stream.close()
            except Exception:  # noqa: BLE001 - never disclose driver/device details
                self.cleanup_failed = True
                raise MediaSourceFailure(MediaFailureCode.MICROPHONE_CLOSE) from None
