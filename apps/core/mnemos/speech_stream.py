"""One-worker partial/final speech stream. Transcripts grant no command authority."""

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from .media import AudioChunk
from .speech import TranscriptSegment, WhisperASR
from .vad import SpeechSegment, SpeechSegmenter


class ASRProvider(Protocol):
    def load(self) -> None: ...
    def transcribe(self, pcm: bytes, language: str = "it") -> list[TranscriptSegment]: ...
    def cancel(self) -> None: ...
    def unload(self) -> None: ...


@dataclass(frozen=True)
class TranscriptUpdate:
    id: str
    source_id: str
    start_seconds: float
    end_seconds: float
    text: str
    language: str
    confidence: float
    partial: bool
    speaker_session_id: str


class StreamingSpeech:
    def __init__(
        self,
        segmenter: SpeechSegmenter | None = None,
        asr: ASRProvider | None = None,
        language: str = "it",
    ):
        if language not in {"it", "en", "auto"}:
            raise ValueError("unsupported speech language")
        self.segmenter, self.asr = segmenter or SpeechSegmenter(), asr or WhisperASR()
        self.language = language
        self.speaker = "anonymous-" + uuid4().hex
        self.utterance = uuid4().hex
        self.partial_at = float("-inf")
        self.discontinuities = 0

    def prepare(self) -> None:
        self.segmenter.provider.probability(bytes(1024))
        self.segmenter.provider.reset()
        self.asr.load()

    def decode(self, segment: SpeechSegment, partial: bool) -> list[TranscriptUpdate]:
        results = self.asr.transcribe(segment.pcm, self.language)
        text = " ".join(result.text for result in results)
        if len(text) > 4096:
            raise RuntimeError("stream transcript budget exceeded")
        # One revision per utterance; a blank result explicitly retracts earlier partial text.
        updates = [
            TranscriptUpdate(
                self.utterance,
                segment.source_id,
                segment.start_seconds + (results[0].start_seconds if results else 0),
                segment.start_seconds + (results[-1].end_seconds if results else 0),
                text,
                results[0].language if results else self.language,
                sum(result.confidence for result in results) / len(results) if results else 0,
                partial,
                self.speaker,
            )
        ]
        if not partial:
            self.utterance = uuid4().hex
            self.partial_at = float("-inf")
        return updates

    def feed(self, chunk: AudioChunk) -> list[TranscriptUpdate]:
        segments = self.segmenter.feed(chunk)
        if self.segmenter.discontinuities != self.discontinuities:
            self.discontinuities = self.segmenter.discontinuities
            self.utterance = uuid4().hex
            self.speaker = "anonymous-" + uuid4().hex
            self.partial_at = float("-inf")
        updates = [update for segment in segments for update in self.decode(segment, False)]
        active = self.segmenter.active
        if active and self.segmenter.voiced >= 3 and len(active) >= 32:
            at = active[-1][0] + 0.032
            if at - self.partial_at >= 0.7:
                segment = SpeechSegment(
                    chunk.source_id, active[0][0], at, b"".join(pcm for _, pcm in active), "partial"
                )
                updates.extend(self.decode(segment, True))
                self.partial_at = at
        return updates

    def flush(self) -> list[TranscriptUpdate]:
        return [
            update for segment in self.segmenter.flush() for update in self.decode(segment, False)
        ]

    def cancel(self) -> None:
        self.asr.cancel()

    def close(self) -> None:
        self.segmenter.close()
        self.asr.unload()
