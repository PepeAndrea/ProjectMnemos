"""Lazy local VAD/ASR providers through the pinned narrow native bridge. No media IO."""

import ctypes as c
import hashlib
import importlib
import json
import math
from dataclasses import dataclass
from typing import Any

from .model_inventory import model_record
from .runtime import ROOT, RuntimeLayout


class SpeechProcessingFailure(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def native_bridge() -> Any:
    layout = RuntimeLayout()
    manifest = json.loads(layout.path("tools/whisper-build/manifest.json").read_text())
    expected = json.loads((ROOT / "docs/native-tools.json").read_text())["whisper"]
    if manifest.get("revision") != expected["revision"]:
        raise ValueError("native runtime revision mismatch")
    source = ROOT / "apps/core/native/whisper_bridge.cpp"
    if hashlib.sha256(source.read_bytes()).hexdigest() != manifest["bridge_source_sha256"]:
        raise ValueError("native bridge source changed; rebuild before loading")
    for artifact in manifest["artifacts"]:
        path = layout.path(artifact["runtime_path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]:
            raise ValueError("native runtime checksum mismatch")
    lib = c.CDLL(str(layout.path("tools/whisper-build/bin/libmnemos-whisper.dylib")))
    if lib.mnemos_bridge_version() != 1:
        raise ValueError("unsupported native bridge ABI")
    lib.mnemos_asr_create.argtypes, lib.mnemos_asr_create.restype = (
        [c.c_char_p, c.c_bool],
        c.c_void_p,
    )
    lib.mnemos_asr_run.argtypes = [c.c_void_p, c.POINTER(c.c_float), c.c_int, c.c_char_p]
    lib.mnemos_asr_running.argtypes, lib.mnemos_asr_running.restype = [c.c_void_p], c.c_bool
    lib.mnemos_asr_count.argtypes = [c.c_void_p]
    lib.mnemos_asr_language.argtypes, lib.mnemos_asr_language.restype = [c.c_void_p], c.c_char_p
    for name in ["start", "end", "confidence", "text"]:
        function = getattr(lib, "mnemos_asr_" + name)
        function.argtypes = [c.c_void_p, c.c_int]
        function.restype = (
            c.c_char_p if name == "text" else c.c_float if name == "confidence" else c.c_double
        )
    for name in ["asr_free", "asr_cancel", "vad_free", "vad_reset"]:
        function = getattr(lib, "mnemos_" + name)
        function.argtypes, function.restype = [c.c_void_p], None
    lib.mnemos_vad_create.argtypes, lib.mnemos_vad_create.restype = [c.c_char_p], c.c_void_p
    lib.mnemos_vad_probability.argtypes = [c.c_void_p, c.POINTER(c.c_float), c.c_int]
    lib.mnemos_vad_probability.restype = c.c_float
    return lib


def pcm_float(pcm: bytes) -> Any:
    np = importlib.import_module("numpy")
    return np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768


class SileroVAD:
    def __init__(self) -> None:
        self.lib: Any = None
        self.context: Any = None

    def load(self) -> None:
        if self.context is None:
            path = model_record("silero-vad")["path"]
            self.lib = native_bridge()
            self.context = self.lib.mnemos_vad_create(str(path).encode())
            if not self.context:
                raise RuntimeError("local VAD unavailable")

    def probability(self, pcm: bytes) -> float:
        if len(pcm) != 1024:
            raise ValueError("VAD requires exactly 512 mono 16kHz PCM16 samples")
        self.load()
        samples = pcm_float(pcm)
        probability = float(
            self.lib.mnemos_vad_probability(
                self.context, samples.ctypes.data_as(c.POINTER(c.c_float)), len(samples)
            )
        )
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise SpeechProcessingFailure("speech-vad-failed")
        return probability

    def reset(self) -> None:
        if self.context is not None:
            self.lib.mnemos_vad_reset(self.context)

    def unload(self) -> None:
        if self.context is not None:
            self.lib.mnemos_vad_free(self.context)
        self.context, self.lib = None, None


@dataclass(frozen=True)
class TranscriptSegment:
    start_seconds: float
    end_seconds: float
    text: str
    confidence: float
    language: str


class WhisperASR:
    """Single-worker provider. Caller owns scheduling/unload; cancel is thread-safe in C++."""

    def __init__(self, gpu: bool = True, model: str = "whisper-tiny"):
        if model not in {"whisper-tiny", "whisper-base"}:
            raise ValueError("unsupported ASR model")
        self.rejected_language_segments = 0
        self.model = model
        self.gpu = gpu
        self.lib: Any = None
        self.context: Any = None

    def load(self) -> None:
        if self.context is None:
            path = model_record(self.model)["path"]
            self.lib = native_bridge()
            self.context = self.lib.mnemos_asr_create(str(path).encode(), self.gpu)
            if not self.context:
                raise RuntimeError("local ASR unavailable")

    def transcribe(self, pcm: bytes, language: str = "it") -> list[TranscriptSegment]:
        if (
            language not in {"auto", "it", "en"}
            or not pcm
            or len(pcm) % 2
            or len(pcm) > 16000 * 2 * 15
        ):
            raise ValueError("ASR requires <=15s mono 16kHz PCM16 and IT/EN/auto language")
        self.load()
        samples = pcm_float(pcm)
        result = self.lib.mnemos_asr_run(
            self.context,
            samples.ctypes.data_as(c.POINTER(c.c_float)),
            len(samples),
            language.encode(),
        )
        if result != 0:
            raise SpeechProcessingFailure("speech-asr-failed")
        detected_language = self.lib.mnemos_asr_language(self.context).decode("ascii")
        if detected_language not in {"it", "en"}:
            # Unsupported auto-detected input retracts the partial segment rather than
            # disabling otherwise healthy sensors. Never translate it or grant authority.
            self.rejected_language_segments += 1
            return []
        segments = []
        duration = len(pcm) / 32000
        count = self.lib.mnemos_asr_count(self.context)
        if not 0 <= count <= 200:
            raise SpeechProcessingFailure("speech-output-invalid")
        for index in range(count):
            text = self.lib.mnemos_asr_text(self.context, index).decode("utf-8").strip()
            start = max(0.0, min(duration, self.lib.mnemos_asr_start(self.context, index)))
            end = max(start, min(duration, self.lib.mnemos_asr_end(self.context, index)))
            confidence = float(self.lib.mnemos_asr_confidence(self.context, index))
            if not math.isfinite(confidence) or not 0 <= confidence <= 1 or len(text) > 4096:
                raise SpeechProcessingFailure("speech-output-invalid")
            if text:
                segments.append(TranscriptSegment(start, end, text, confidence, detected_language))
        return segments

    def running(self) -> bool:
        return bool(self.context and self.lib.mnemos_asr_running(self.context))

    def cancel(self) -> None:
        if self.context is not None:
            self.lib.mnemos_asr_cancel(self.context)

    def unload(self) -> None:
        if self.context is not None:
            self.lib.mnemos_asr_free(self.context)
        self.context, self.lib = None, None
