"""Bounded native/replay ingestion, volatile buffers and sampled local perception."""

import asyncio
import importlib
import queue
import threading
import time
from dataclasses import asdict
from typing import Any
from uuid import UUID, uuid4

from .face_quality import inspect_face_crop
from .media import (
    AudioChunk,
    AudioSource,
    MediaSourceFailure,
    MicrophoneSource,
    OpenCVVideoSource,
    SourceClock,
    VideoFrame,
    VideoSource,
    WaveAudioSource,
)
from .reference_quality import inspect_crop
from .runtime import MediaChunk, RollingBuffer, RuntimeLayout
from .session_names import SessionNames
from .speech import SpeechProcessingFailure
from .speech_stream import StreamingSpeech, TranscriptUpdate
from .tracking import SessionTracker, TrackUpdate
from .vision import DetectorProvider, YOLOXProvider, YuNetProvider
from .voice_enrollment import VoiceEnrollmentInbox


class CaptureSession:
    def __init__(
        self,
        video: VideoSource | None,
        audio: AudioSource | None,
        detector: DetectorProvider | None = None,
        faces: DetectorProvider | None = None,
        inference_fps: float = 5,
        speech: StreamingSpeech | None = None,
        clock: SourceClock | None = None,
    ):
        if video is None and audio is None or not 0 < inference_fps <= 30:
            raise ValueError("invalid capture configuration")
        self.id = str(uuid4())
        self.enrollment = VoiceEnrollmentInbox(self.id)
        self.session_names = SessionNames()
        self.video, self.audio = video, audio
        self.detector, self.faces = detector or YOLOXProvider(), faces or YuNetProvider()
        if speech is not None and audio is None:
            raise ValueError("transcription requires an audio source")
        self.speech, self.clock = speech, clock
        self.audio_queue: queue.Queue[AudioChunk] = queue.Queue(maxsize=128)
        self.transcripts: dict[str, dict[str, Any]] = {}
        self.audio_drops = 0
        self.speech_latency_ms = 0.0
        self.speech_discontinuities = 0
        self.inference_fps = inference_fps
        self.video_queue: queue.Queue[VideoFrame] = queue.Queue(maxsize=2)
        self.video_buffer = RollingBuffer(max_bytes=64 * 1024 * 1024)
        self.audio_buffer = RollingBuffer(max_bytes=16 * 1024 * 1024)
        self.tracker = SessionTracker()
        self.stop_event = threading.Event()
        self.audio_done = threading.Event()
        self.video_done = threading.Event()
        self.speech_done = threading.Event()
        self.lock = threading.RLock()
        self.state = "idle"
        self.error: str | None = None
        self.error_code: str | None = None
        self.jpeg: bytes | None = None
        self.width = self.height = 0
        self.detections: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.visible_tracks: dict[str, dict[str, Any]] = {}
        self.face_landmarks: dict[str, tuple[tuple[float, float], ...]] = {}
        self.track_bindings: dict[str, str] = {}
        self.binding_claims: dict[str, str] = {}
        self.last_observed = 0.0
        self.reference_frame: VideoFrame | None = None
        self.video_frames = self.audio_chunks = self.processed_frames = self.drops = 0
        self.last_latency_ms = 0.0
        self.started = time.monotonic()
        self.task: asyncio.Task[None] | None = None

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            self.session_names.prune(self.visible_tracks, self.last_observed)
            return {
                "id": self.id,
                "state": self.state,
                "error": self.error,
                "error_code": self.error_code,
                "worker_active": self.task is not None and not self.task.done(),
                "source_cleanup_failed": bool(
                    getattr(self.video, "cleanup_failed", False)
                    or getattr(self.audio, "cleanup_failed", False)
                ),
                "video_frames": self.video_frames,
                "audio_chunks": self.audio_chunks,
                "processed_frames": self.processed_frames,
                "drops": self.drops,
                "queue_depth": self.video_queue.qsize(),
                "latency_ms": self.last_latency_ms,
                "process_fps": self.processed_frames / max(0.001, time.monotonic() - self.started),
                "audio_buffer_bytes": self.audio_buffer.bytes_used,
                "video_buffer_bytes": self.video_buffer.bytes_used,
                "detections": list(self.detections),
                "events": list(self.events),
                "tracks": [
                    {
                        **value,
                        "entity_id": self.track_bindings.get(key),
                        "session_name": self.session_names.labels.get(key),
                    }
                    for key, value in self.visible_tracks.items()
                ],
                "recording": False,
                "camera": self.video is not None,
                "microphone": self.audio is not None,
                "transcribing": self.speech is not None
                and self.state in {"starting", "running"}
                and not self.speech_done.is_set(),
                "transcripts": list(self.transcripts.values()),
                "enrollment_proposals": self.enrollment.snapshot(),
                "audio_queue_depth": self.audio_queue.qsize(),
                "audio_drops": self.audio_drops,
                "audio_ended": self.audio_done.is_set(),
                "video_ended": self.video_done.is_set(),
                "speech_latency_ms": self.speech_latency_ms,
                "speech_discontinuities": self.speech_discontinuities,
                "speech_language": getattr(self.speech, "language", None),
                "speech_rejected_language_segments": getattr(
                    getattr(self.speech, "asr", None), "rejected_language_segments", 0
                )
                if self.speech
                else 0,
                "width": self.width,
                "height": self.height,
            }

    def start(self) -> None:
        if self.task is not None:
            raise RuntimeError("capture already started")
        self.state = "starting" if self.speech else "running"
        self.task = asyncio.create_task(self.run())

    def fail(self, error: str, error_code: str | None = None) -> None:
        with self.lock:
            # Keep the first source/model failure when secondary cleanup also fails.
            if self.error is None:
                self.error, self.error_code = error, error_code
            self.state = "failed"
            self.stop_event.set()
            if self.speech:
                self.speech.cancel()
            self.clear_media()

    def produce_video(self) -> None:
        assert self.video is not None
        last_buffer = float("-inf")
        try:
            cv, np = importlib.import_module("cv2"), importlib.import_module("numpy")
            for frame in self.video.frames():
                if self.stop_event.is_set():
                    break
                delay = frame.monotonic_seconds - time.monotonic()
                if delay > 0 and self.stop_event.wait(delay):
                    break
                with self.lock:
                    self.video_frames += 1
                # Compressed, sampled buffer, independent from inference queue drops.
                if frame.monotonic_seconds - last_buffer >= 1:
                    pixels = np.frombuffer(frame.pixels, np.uint8).reshape(
                        frame.height, frame.width, 3
                    )
                    small = cv.resize(pixels, (320, max(1, int(frame.height * 320 / frame.width))))
                    ok, encoded = cv.imencode(".jpg", small, [cv.IMWRITE_JPEG_QUALITY, 55])
                    if not ok:
                        raise ValueError("buffer encoding failed")
                    with self.lock:
                        if not self.stop_event.is_set():
                            self.video_buffer.append(
                                MediaChunk(frame.monotonic_seconds, encoded.tobytes())
                            )
                    last_buffer = frame.monotonic_seconds
                with self.lock:
                    if self.stop_event.is_set():
                        break
                    if self.video_queue.full():
                        try:
                            self.video_queue.get_nowait()
                            self.drops += 1
                        except queue.Empty:
                            pass
                    self.video_queue.put_nowait(frame)
        except MediaSourceFailure as exc:
            if not self.stop_event.is_set():
                self.fail("video source or normalization failed", exc.code)
        except Exception:  # noqa: BLE001 - worker boundary fails closed without logging private media
            if not self.stop_event.is_set():
                self.fail("video source or normalization failed", "video-source-failed")
        finally:
            self.video_done.set()
            self.video.close()

    def produce_audio(self) -> None:
        assert self.audio is not None
        try:
            for chunk in self.audio.chunks():
                if self.stop_event.is_set():
                    break
                delay = chunk.monotonic_seconds - time.monotonic()
                if delay > 0 and self.stop_event.wait(delay):
                    break
                with self.lock:
                    if not self.stop_event.is_set():
                        self.audio_buffer.append(MediaChunk(chunk.monotonic_seconds, chunk.samples))
                        self.audio_chunks += 1
                        if self.speech:
                            if self.audio_queue.full():
                                try:
                                    self.audio_queue.get_nowait()
                                    self.audio_drops += 1
                                except queue.Empty:
                                    pass
                            self.audio_queue.put_nowait(chunk)
        except MediaSourceFailure as exc:
            if not self.stop_event.is_set():
                self.fail("audio source or normalization failed", exc.code)
        except Exception:  # noqa: BLE001 - worker boundary fails closed without logging private media
            if not self.stop_event.is_set():
                self.fail("audio source or normalization failed", "audio-source-failed")
        finally:
            self.audio_done.set()
            self.audio.close()

    def process(self) -> None:
        last_processed = float("-inf")
        try:
            cv, np = importlib.import_module("cv2"), importlib.import_module("numpy")
            while not self.stop_event.is_set():
                try:
                    frame = self.video_queue.get(timeout=0.1)
                except queue.Empty:
                    if self.video_done.is_set():
                        break
                    continue
                if frame.monotonic_seconds - last_processed < 1 / self.inference_fps:
                    with self.lock:
                        self.drops += 1
                    continue
                start = time.perf_counter()
                detections = self.detector.detect(frame) + self.faces.detect(frame)
                pixels = np.frombuffer(frame.pixels, np.uint8).reshape(frame.height, frame.width, 3)
                ok, encoded = cv.imencode(".jpg", pixels, [cv.IMWRITE_JPEG_QUALITY, 65])
                if not ok:
                    raise ValueError("preview encoding failed")
                with self.lock:
                    if self.stop_event.is_set():
                        break
                    updates = self.tracker.update(detections, frame.source_id, frame.sequence)
                    self.publish_tracks(updates, frame.monotonic_seconds)
                    self.reference_frame = frame
                    self.jpeg = encoded.tobytes()
                    self.width, self.height = frame.width, frame.height
                    self.detections = [d.public_payload() for d in detections]
                    self.events = (
                        self.events
                        + [
                            {
                                "kind": u.kind,
                                "track_id": u.track_id,
                                "detection": u.detection.public_payload(),
                            }
                            for u in updates
                        ]
                    )[-100:]
                    self.processed_frames += 1
                    self.last_latency_ms = (time.perf_counter() - start) * 1000
                last_processed = frame.monotonic_seconds
        except Exception:  # noqa: BLE001 - worker boundary fails closed without logging private media
            self.fail("local perception unavailable")
        finally:
            self.detector.unload()
            self.faces.unload()
            self.tracker.clear()

    def publish_speech(self, updates: list[TranscriptUpdate]) -> None:
        with self.lock:
            if self.stop_event.is_set():
                return
            for update in updates:
                self.enrollment.offer(update)
                self.session_names.offer(update, self.visible_tracks, self.last_observed)
                self.transcripts.pop(update.id, None)
                if update.text:
                    self.transcripts[update.id] = asdict(update)
                while len(self.transcripts) > 50:
                    del self.transcripts[next(iter(self.transcripts))]

    def object_crop(self, track_id: UUID, entity_id: UUID) -> tuple[bytes, dict[str, Any]]:
        with self.lock:
            key = str(track_id)
            frame = self.reference_frame
            row = self.visible_tracks.get(key)
            if (
                self.state != "running"
                or self.stop_event.is_set()
                or frame is None
                or row is None
                or self.track_bindings.get(key) != str(entity_id)
                or not 0 <= time.monotonic() - self.last_observed <= 2
            ):
                raise KeyError("fresh explicitly bound object frame required")
            if row["label"] in {"person", "face"}:
                raise PermissionError("person references require dedicated consent")
            if (
                frame.pixel_format != "bgr24"
                or row["source_id"] != frame.source_id
                or row["sequence"] != frame.sequence
            ):
                raise ValueError("reference requires the current normalized detector frame")
            box = row["box"]
            x, y, width, height = (int(box[value]) for value in ("x", "y", "width", "height"))
            if (
                x < 0
                or y < 0
                or width < 32
                or height < 32
                or x + width > frame.width
                or y + height > frame.height
            ):
                raise ValueError("fully visible object crop at least 32px required")
            for detection in self.detections:
                other = detection["box"]
                if detection["label"] in {"face", "person"} and (
                    min(x + width, other["x"] + other["width"]) > max(x, other["x"])
                    and min(y + height, other["y"] + other["height"]) > max(y, other["y"])
                ):
                    raise PermissionError("object crop overlaps a person; clear the view first")
            provenance = {
                "capture_id": self.id,
                "track_id": key,
                "source_id": frame.source_id,
                "sequence": frame.sequence,
                "observed_at": frame.wall_time.isoformat(),
                "label": row["label"],
                "box": box,
                "method": "explicit-owner-object-crop",
            }
        # Selected snapshot remains owned by this explicit operation; Stop clears the
        # source's live reference without blocking encoding/storage workers.
        cv, np = importlib.import_module("cv2"), importlib.import_module("numpy")
        pixels = np.frombuffer(frame.pixels, np.uint8).reshape(frame.height, frame.width, 3)
        crop = pixels[y : y + height, x : x + width]
        if max(width, height) > 1600:
            crop = cv.resize(
                crop,
                (
                    max(1, int(width * 1600 / max(width, height))),
                    max(1, int(height * 1600 / max(width, height))),
                ),
            )
        provenance["quality"] = inspect_crop(crop)
        ok, encoded = cv.imencode(".jpg", crop, [cv.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            raise ValueError("object crop encoding failed")
        return encoded.tobytes(), provenance

    def face_crop(self, track_id: UUID) -> tuple[bytes, dict[str, Any]]:
        """Explicit selection only; no persistent track name or biometric identity inference."""
        with self.lock:
            frame = self.reference_frame
            row = self.visible_tracks.get(str(track_id))
            if (
                self.state != "running"
                or self.stop_event.is_set()
                or frame is None
                or row is None
                or not 0 <= time.monotonic() - self.last_observed <= 2
            ):
                raise KeyError("fresh face frame required")
            if row["label"] != "face":
                raise PermissionError("only a detected face can supply this reference")
            if (
                frame.pixel_format != "bgr24"
                or row["source_id"] != frame.source_id
                or row["sequence"] != frame.sequence
            ):
                raise ValueError("current normalized detector frame required")
            box = row["box"]
            x, y, width, height = (int(box[value]) for value in ("x", "y", "width", "height"))
            if (
                x < 0
                or y < 0
                or width < 64
                or height < 64
                or x + width > frame.width
                or y + height > frame.height
            ):
                raise ValueError("fully visible face crop at least 64px required")
            for detection in self.detections:
                other = detection["box"]
                if (
                    detection["label"] == "face"
                    and other != box
                    and (
                        min(x + width, other["x"] + other["width"]) > max(x, other["x"])
                        and min(y + height, other["y"] + other["height"]) > max(y, other["y"])
                    )
                ):
                    raise PermissionError("selected face overlaps another detected face")
            provenance = {
                "capture_id": self.id,
                "track_id": str(track_id),
                "source_id": frame.source_id,
                "sequence": frame.sequence,
                "observed_at": frame.wall_time.isoformat(),
                "box": box,
                "method": "explicit-owner-face-crop",
            }
            landmarks = self.face_landmarks.get(str(track_id), ())
        cv, np = importlib.import_module("cv2"), importlib.import_module("numpy")
        pixels = np.frombuffer(frame.pixels, np.uint8).reshape(frame.height, frame.width, 3)
        crop = pixels[y : y + height, x : x + width]
        if max(width, height) > 1600:
            crop = cv.resize(
                crop,
                (
                    max(1, int(width * 1600 / max(width, height))),
                    max(1, int(height * 1600 / max(width, height))),
                ),
            )
        provenance["quality"] = inspect_face_crop(crop, landmarks, (x, y), (width, height))
        ok, encoded = cv.imencode(".jpg", crop, [cv.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            raise ValueError("face crop encoding failed")
        return encoded.tobytes(), provenance

    def publish_tracks(self, updates: list[TrackUpdate], observed: float) -> None:
        """Called under lock; only current detections remain selectable."""
        self.last_observed = observed
        self.visible_tracks = {
            update.track_id: {"track_id": update.track_id, **update.detection.public_payload()}
            for update in updates
            if update.kind != "exit"
        }
        self.session_names.observe(self.visible_tracks, observed)
        self.face_landmarks = {
            update.track_id: update.detection.landmarks
            for update in updates
            if update.kind != "exit" and update.detection.label == "face"
        }
        # A missed frame invalidates human binding, rather than transferring a name
        # through an ambiguous/lost association. Reappearance needs new evidence.
        self.track_bindings = {
            key: value for key, value in self.track_bindings.items() if key in self.visible_tracks
        }
        self.binding_claims = {
            key: value for key, value in self.binding_claims.items() if key in self.visible_tracks
        }

    def name_face(self, track_id: UUID, name: str) -> None:
        with self.lock:
            if self.state != "running" or self.stop_event.is_set():
                raise ValueError("capture is no longer active")
            self.session_names.assign(str(track_id), name, self.visible_tracks, self.last_observed)

    def claim_track(self, track_id: UUID) -> dict[str, Any]:
        with self.lock:
            key = str(track_id)
            if self.state != "running" or self.stop_event.is_set():
                raise ValueError("capture is no longer active")
            row = self.visible_tracks.get(key)
            if row is None or not 0 <= time.monotonic() - self.last_observed <= 2:
                raise KeyError(key)
            if row["label"] in {"person", "face"}:
                raise PermissionError("person tracks require dedicated biometric enrollment")
            if key in self.binding_claims or key in self.track_bindings:
                raise ValueError("track already bound or being reviewed")
            claim_id = str(uuid4())
            self.binding_claims[key] = claim_id
            return {**row, "claim_id": claim_id}

    def finish_binding(self, track_id: UUID, entity_id: UUID | None, claim_id: str) -> bool:
        with self.lock:
            key = str(track_id)
            claimed = self.binding_claims.get(key) == claim_id
            if claimed:
                del self.binding_claims[key]
            if (
                claimed
                and entity_id is not None
                and self.state == "running"
                and not self.stop_event.is_set()
                and key in self.visible_tracks
                and 0 <= time.monotonic() - self.last_observed <= 2
            ):
                self.track_bindings[key] = str(entity_id)
                return True
            return False

    def process_speech(self) -> None:
        assert self.speech is not None
        try:
            while not self.stop_event.is_set():
                try:
                    chunk = self.audio_queue.get(timeout=0.1)
                except queue.Empty:
                    if self.audio_done.is_set():
                        self.publish_speech(self.speech.flush())
                        break
                    continue
                start = time.perf_counter()
                updates = self.speech.feed(chunk)
                with self.lock:
                    if self.speech.discontinuities != self.speech_discontinuities:
                        self.transcripts = {
                            key: value
                            for key, value in self.transcripts.items()
                            if not value["partial"]
                        }
                self.publish_speech(updates)
                with self.lock:
                    self.speech_latency_ms = (time.perf_counter() - start) * 1000
                    self.speech_discontinuities = self.speech.discontinuities
        except SpeechProcessingFailure as exc:
            if not self.stop_event.is_set():
                self.fail("local speech processing unavailable", exc.code)
        except Exception:  # noqa: BLE001 - fail closed; private transcript/audio never logged
            if not self.stop_event.is_set():
                self.fail("local speech processing unavailable", "speech-processing-failed")
        finally:
            with self.lock:
                try:
                    self.speech.close()
                finally:
                    self.audio_buffer.clear()
                    self.speech_done.set()

    async def run(self) -> None:
        done = threading.Event()
        expiry = None
        consumers = []
        producers = []
        try:
            if self.speech:
                await asyncio.to_thread(self.speech.prepare)
            if self.stop_event.is_set():
                return
            if self.clock:
                self.clock.reset()
            with self.lock:
                self.state = "running"
                self.started = time.monotonic()
            expiry = asyncio.create_task(self.expire_buffers(done))
            if self.video is not None:
                consumers.append(asyncio.create_task(asyncio.to_thread(self.process)))
                producers.append(asyncio.create_task(asyncio.to_thread(self.produce_video)))
            if self.speech:
                consumers.append(asyncio.create_task(asyncio.to_thread(self.process_speech)))
            if self.audio is not None:
                producers.append(asyncio.create_task(asyncio.to_thread(self.produce_audio)))
            results = await asyncio.gather(*producers, return_exceptions=True)
            if any(isinstance(result, BaseException) for result in results):
                self.fail("capture producer cleanup failed")
        except Exception:  # noqa: BLE001 - startup boundary, no private logs
            self.fail("capture source or model startup failed")
        finally:
            done.set()
            if expiry is not None:
                await expiry
            results = await asyncio.gather(*consumers, return_exceptions=True)
            if any(isinstance(result, BaseException) for result in results):
                self.fail("capture worker cleanup failed")
            with self.lock:
                try:
                    if self.speech and not consumers:
                        self.speech.close()
                    if self.video is not None:
                        self.video.close()
                    if self.audio is not None:
                        self.audio.close()
                except Exception:  # noqa: BLE001 - cleanup boundary must still clear private media
                    self.fail("capture source cleanup failed", "sensor-cleanup-failed")
                finally:
                    if self.state == "running":
                        self.state = "completed"
                    self.clear_media()

    async def expire_buffers(self, done: threading.Event) -> None:
        while not done.is_set() and not self.stop_event.is_set():
            with self.lock:
                at = time.monotonic()
                if at - self.last_observed > 2:
                    self.reference_frame = None
                    self.face_landmarks.clear()
                self.enrollment.expire()
                self.audio_buffer.expire(at)
                self.video_buffer.expire(at)
                self.transcripts = {
                    key: value
                    for key, value in self.transcripts.items()
                    if value["end_seconds"] >= at - 300
                }
            await asyncio.sleep(0.1)

    def clear_media(self) -> None:
        self.video_buffer.clear()
        self.audio_buffer.clear()
        self.jpeg = None
        self.detections = []
        self.visible_tracks.clear()
        self.face_landmarks.clear()
        self.track_bindings.clear()
        self.binding_claims.clear()
        self.reference_frame = None
        self.transcripts.clear()
        self.enrollment.clear()
        self.session_names.clear()
        while not self.video_queue.empty():
            try:
                self.video_queue.get_nowait()
            except queue.Empty:
                break

        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

    async def stop(self) -> None:
        self.stop_event.set()
        with self.lock:
            if self.speech:
                self.speech.cancel()
            self.clear_media()
        if self.task is not None:
            try:
                await asyncio.wait_for(asyncio.shield(self.task), timeout=5)
            except TimeoutError:
                self.fail("capture worker unresponsive; source permission/device recovery required")
                return
        with self.lock:
            self.state = "stopped"
            self.events = []


def build_capture(
    mode: str,
    camera: bool,
    microphone: bool,
    camera_consent: bool,
    microphone_consent: bool,
    layout: RuntimeLayout | None = None,
    *,
    transcribe: bool = False,
    language: str = "it",
    camera_index: int | None = None,
) -> CaptureSession:
    layout = layout or RuntimeLayout()
    clock = SourceClock()
    video: VideoSource | None = None
    audio: AudioSource | None = None
    if mode == "native":
        if camera:
            # macOS device ordering can put Continuity Camera at index 0 even when it is
            # unavailable. Probe a small bounded set after explicit dashboard consent.
            camera_source: int | tuple[int, ...] = (
                camera_index if camera_index is not None else (0, 1, 2, 3, 4)
            )
            video = OpenCVVideoSource(camera_source, clock=clock, device_authorized=camera_consent)
        if microphone:
            audio = MicrophoneSource(clock=clock, device_authorized=microphone_consent)
    elif mode == "replay":
        if camera:
            video = OpenCVVideoSource(
                layout.path("datasets/perception-replay/replay.avi"), clock=clock
            )
        if microphone:
            audio = WaveAudioSource(layout.path("datasets/perception-replay/tone.wav"), clock=clock)
    elif mode == "speech-replay":
        if camera or not microphone:
            raise ValueError("speech replay requires microphone-only configuration")
        filename = "stream.wav" if language == "en" else "stream-it.wav"
        audio = WaveAudioSource(layout.path("datasets/speech-synthetic/" + filename), clock=clock)
    else:
        raise ValueError("unsupported capture mode")
    return CaptureSession(
        video, audio, speech=StreamingSpeech(language=language) if transcribe else None, clock=clock
    )
