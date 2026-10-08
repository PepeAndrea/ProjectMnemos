import os
from datetime import UTC, datetime

import pytest
from mnemos.media import AudioChunk
from mnemos.speech import SileroVAD, WhisperASR
from mnemos.vad import SpeechSegmenter


class FakeVAD:
    def __init__(self, values):
        self.values = iter(values)
        self.resets = 0
        self.unloaded = False

    def probability(self, pcm):
        assert len(pcm) == 1024
        return next(self.values)

    def reset(self):
        self.resets += 1

    def unload(self):
        self.unloaded = True


def chunk(index, source="synthetic", seconds=None):
    return AudioChunk(
        source,
        index,
        index * 0.032 if seconds is None else seconds,
        datetime.now(UTC),
        16000,
        1,
        "s16le",
        bytes(1024),
    )


def test_speech_endpoint_pre_roll_and_timecodes():
    provider = FakeVAD([0] * 10 + [0.9] * 10 + [0] * 15)
    segmenter = SpeechSegmenter(provider)
    segments = []
    for index in range(35):
        segments.extend(segmenter.feed(chunk(index)))
    assert len(segments) == 1 and segments[0].reason == "silence"
    assert segments[0].start_seconds == pytest.approx(0.096)
    assert segments[0].end_seconds == pytest.approx(35 * 0.032)
    assert len(segments[0].pcm) == 32 * 1024
    assert segmenter.flush() == []
    segmenter.close()
    assert provider.unloaded and not segmenter.pending and not segmenter.active


def test_duration_limit_discontinuity_and_short_click_rejection():
    provider = FakeVAD([0.9] * 100)
    segmenter = SpeechSegmenter(provider, max_seconds=0.5)
    segments = []
    for index in range(60):
        segments.extend(segmenter.feed(chunk(index)))
        assert len(segmenter.active) <= 15
    assert len(segments) == 4 and all(len(segment.pcm) <= 16000 for segment in segments)
    segmenter.feed(chunk(61))
    assert segmenter.discontinuities == 1 and provider.resets == 1
    assert segmenter.flush() == []
    segmenter.close()
    short = SpeechSegmenter(FakeVAD([0.9] + [0] * 15))
    assert not [segment for index in range(16) for segment in short.feed(chunk(index))]
    short.close()


def test_split_pcm_chunk_boundaries_and_invalid_probability():
    segmenter = SpeechSegmenter(FakeVAD([0.8] * 4))
    for index in range(8):
        audio = AudioChunk(
            "test", index, index * 0.016, datetime.now(UTC), 16000, 1, "s16le", bytes(512)
        )
        segmenter.feed(audio)
        assert len(segmenter.pending) < 1024
    assert len(segmenter.flush()[0].pcm) == 4096
    segmenter.close()
    broken = SpeechSegmenter(FakeVAD([float("nan")]))
    with pytest.raises(RuntimeError):
        broken.feed(chunk(0))
    broken.close()


def test_invalid_input_rejected_before_loading_native_runtime():
    vad = SileroVAD()
    asr = WhisperASR()
    with pytest.raises(ValueError):
        vad.probability(b"x")
    for data, language in [(b"", "it"), (b"x", "it"), (bytes(500000), "en"), (bytes(1024), "fr")]:
        with pytest.raises(ValueError):
            asr.transcribe(data, language)
    assert vad.context is None and asr.context is None


@pytest.mark.skipif(not os.environ.get("MNEMOS_TEST_SPEECH"), reason="native speech runtime opt-in")
def test_real_silero_silence_and_unload():
    vad = SileroVAD()
    try:
        assert all(vad.probability(bytes(1024)) < 0.35 for _ in range(20))
    finally:
        vad.unload()
    assert vad.context is None


def test_partial_final_revisions_and_gap_never_grant_speaker_identity():
    from mnemos.speech import TranscriptSegment
    from mnemos.speech_stream import StreamingSpeech

    class FakeASR:
        def __init__(self):
            self.cancelled = self.unloaded = False

        def transcribe(self, pcm, language):
            return [TranscriptSegment(0, len(pcm) / 32000, "synthetic text", 0.9, "it")]

        def cancel(self):
            self.cancelled = True

        def unload(self):
            self.unloaded = True

    asr = FakeASR()
    stream = StreamingSpeech(
        SpeechSegmenter(FakeVAD([0.9] * 60 + [0] * 15 + [0.9] * 40)), asr, "it"
    )
    updates = []
    for index in range(75):
        updates.extend(stream.feed(chunk(index)))
    assert any(update.partial for update in updates) and not updates[-1].partial
    assert len({update.id for update in updates}) == 1
    assert all(update.speaker_session_id.startswith("anonymous-") for update in updates)
    previous = updates[-1]
    for index in range(77, 117):
        updates.extend(stream.feed(chunk(index)))
    assert updates[-1].speaker_session_id != previous.speaker_session_id
    assert updates[-1].id != previous.id
    stream.cancel()
    stream.close()
    assert asr.cancelled and asr.unloaded


def test_wer_accounts_for_insertions_deletions_and_punctuation():
    from mnemos.speech_benchmark import word_error_rate

    assert word_error_rate("Ciao, Tobi!", "ciao tobi") == 0
    assert word_error_rate("il mio zaino", "il mio giallo") == pytest.approx(1 / 3)
    assert word_error_rate("my bag", "my blue bag") == 0.5


@pytest.mark.skipif(not os.environ.get("MNEMOS_TEST_SPEECH"), reason="native speech runtime opt-in")
def test_real_synthesized_stream_and_model_eviction():
    from mnemos.runtime import RuntimeLayout
    from mnemos.speech_benchmark import read_pcm
    from mnemos.speech_stream import StreamingSpeech

    pcm = read_pcm(RuntimeLayout().path("datasets/speech-synthetic/english.wav")) + bytes(32000)
    stream = StreamingSpeech(language="en")
    updates = []
    try:
        for index, offset in enumerate(range(0, len(pcm) - 1023, 1024)):
            audio = AudioChunk(
                "synthetic-English",
                index,
                index * 0.032,
                datetime.now(UTC),
                16000,
                1,
                "s16le",
                pcm[offset : offset + 1024],
            )
            updates.extend(stream.feed(audio))
        updates.extend(stream.flush())
        final = [update for update in updates if not update.partial and update.text]
        assert final and "backpack" in final[-1].text.lower()
        assert 0 <= final[-1].start_seconds <= final[-1].end_seconds <= len(pcm) / 32000
        assert all(update.language == "en" for update in updates)
    finally:
        stream.close()
    assert stream.asr.context is None and stream.segmenter.provider.context is None


@pytest.mark.skipif(not os.environ.get("MNEMOS_TEST_SPEECH"), reason="native cancellation opt-in")
def test_real_native_inference_can_be_cancelled_and_stays_cancelled():
    import time
    from concurrent.futures import ThreadPoolExecutor

    from mnemos.runtime import RuntimeLayout
    from mnemos.speech_benchmark import read_pcm

    pcm = read_pcm(RuntimeLayout().path("datasets/speech-synthetic/english.wav"))
    provider = WhisperASR(gpu=False)
    provider.load()
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(provider.transcribe, (pcm * 6)[:480000], "en")
            deadline = time.monotonic() + 5
            while not provider.running() and not future.done() and time.monotonic() < deadline:
                time.sleep(0.001)
            assert provider.running(), "native run never became observable"
            provider.cancel()
            with pytest.raises(RuntimeError, match="speech-asr-failed"):
                future.result(timeout=5)
        with pytest.raises(RuntimeError, match="speech-asr-failed"):
            provider.transcribe(pcm, "en")
    finally:
        provider.unload()
    assert provider.context is None


def test_italian_default_and_unsupported_auto_language_does_not_stop_stream():
    from mnemos.api import CaptureRequest
    from mnemos.speech_stream import StreamingSpeech

    class Bridge:
        language = b"fr"

        def mnemos_asr_run(self, *args):
            return 0

        def mnemos_asr_language(self, *args):
            return self.language

        def mnemos_asr_count(self, *args):
            return 0

    assert CaptureRequest().language == StreamingSpeech().language == "it"
    provider = WhisperASR()
    provider.context = object()
    provider.lib = Bridge()
    assert provider.transcribe(bytes(1024), "auto") == []
    assert provider.rejected_language_segments == 1
    provider.lib.language = b"it"
    assert provider.transcribe(bytes(1024), "it") == []
    assert provider.rejected_language_segments == 1


def test_speech_failure_code_is_static_not_driver_text():
    from mnemos.speech import SpeechProcessingFailure

    class Bridge:
        def mnemos_asr_run(self, *args):
            return 1

    provider = WhisperASR()
    provider.context = object()
    provider.lib = Bridge()
    with pytest.raises(SpeechProcessingFailure) as exc:
        provider.transcribe(bytes(1024), "it")
    assert exc.value.code == str(exc.value) == "speech-asr-failed"


def test_default_speech_replay_reads_italian_fixture_without_opening_sensors():
    from mnemos.capture import build_capture

    capture = build_capture("speech-replay", False, True, False, False, transcribe=True)
    assert capture.speech.language == "it"
    assert capture.audio.path.name == "stream-it.wav"
    assert capture.task is None and capture.video is None
