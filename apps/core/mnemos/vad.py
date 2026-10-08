"""Bounded streaming speech segmentation over normalized mono 16kHz PCM."""

import math
from collections import deque
from dataclasses import dataclass
from typing import Protocol

from .media import AudioChunk
from .speech import SileroVAD


class VADProvider(Protocol):
    def probability(self, pcm: bytes) -> float: ...
    def reset(self) -> None: ...
    def unload(self) -> None: ...


@dataclass(frozen=True)
class SpeechSegment:
    source_id: str
    start_seconds: float
    end_seconds: float
    pcm: bytes
    reason: str


class SpeechSegmenter:
    def __init__(self, provider: VADProvider | None = None, max_seconds: float = 15):
        if not 0.5 <= max_seconds <= 15:
            raise ValueError("speech segment duration outside budget")
        self.provider = provider or SileroVAD()
        self.max_frames = int(max_seconds / 0.032)
        self.pre: deque[tuple[float, bytes]] = deque(maxlen=7)
        self.active: list[tuple[float, bytes]] = []
        self.pending = b""
        self.source_id: str | None = None
        self.sequence = -1
        self.pending_at = 0.0
        self.expected_at = 0.0
        self.voiced = self.silence = 0
        self.last_probability = 0.0
        self.discontinuities = 0

    def reset(self) -> None:
        self.pre.clear()
        self.active.clear()
        self.pending = b""
        self.source_id = None
        self.sequence = -1
        self.voiced = self.silence = 0
        self.provider.reset()

    def finish(self, reason: str) -> SpeechSegment | None:
        result = None
        if self.active and self.voiced >= 3:
            result = SpeechSegment(
                self.source_id or "",
                self.active[0][0],
                self.active[-1][0] + 0.032,
                b"".join(pcm for _, pcm in self.active),
                reason,
            )
        self.active.clear()
        self.pre.clear()
        self.voiced = self.silence = 0
        return result

    def feed(self, chunk: AudioChunk) -> list[SpeechSegment]:
        if chunk.sample_rate != 16000 or chunk.channels != 1:
            raise ValueError("VAD stream requires normalized 16kHz mono")
        if self.source_id is not None and (
            chunk.source_id != self.source_id
            or chunk.sequence != self.sequence + 1
            or abs(chunk.monotonic_seconds - self.expected_at) > 0.05
        ):
            # Never join speech across a dropped packet, reconnect or source switch.
            self.reset()
            self.discontinuities += 1
        if self.source_id is None:
            self.source_id = chunk.source_id
            self.pending_at = chunk.monotonic_seconds
        self.sequence = chunk.sequence
        self.expected_at = chunk.monotonic_seconds + len(chunk.samples) / 32000
        self.pending += chunk.samples
        results = []
        while len(self.pending) >= 1024:
            pcm, self.pending = self.pending[:1024], self.pending[1024:]
            at, self.pending_at = self.pending_at, self.pending_at + 0.032
            probability = self.provider.probability(pcm)
            if not math.isfinite(probability) or not 0 <= probability <= 1:
                raise RuntimeError("invalid VAD provider probability")
            self.last_probability = probability
            if not self.active:
                if probability >= 0.6:
                    self.active = list(self.pre) + [(at, pcm)]
                    self.pre.clear()
                    self.voiced, self.silence = 1, 0
                else:
                    self.pre.append((at, pcm))
                continue
            self.active.append((at, pcm))
            self.voiced += int(probability >= 0.6)
            self.silence = self.silence + 1 if probability < 0.35 else 0
            if self.silence >= 15 or len(self.active) >= self.max_frames:
                segment = self.finish("silence" if self.silence >= 15 else "duration-limit")
                if segment is not None:
                    results.append(segment)
        return results

    def flush(self) -> list[SpeechSegment]:
        result = self.finish("source-end")
        self.pending = b""
        return [result] if result else []

    def close(self) -> None:
        self.reset()
        self.provider.unload()
