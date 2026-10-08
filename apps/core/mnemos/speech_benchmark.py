"""Compare pinned local ASR backends on non-private, locally synthesized IT/EN fixtures."""

import hashlib
import json
import re
import resource
import time
import wave
from pathlib import Path

from .metrics import Metrics
from .runtime import RuntimeLayout
from .speech import SileroVAD, WhisperASR


def word_error_rate(expected: str, actual: str) -> float:
    words = re.compile(r"[^\W_]+", re.UNICODE)
    left, right = words.findall(expected.lower()), words.findall(actual.lower())
    if not left:
        raise ValueError("WER requires a nonempty reference")
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1] / len(left)


def read_pcm(path: Path) -> bytes:
    with wave.open(str(path)) as stream:
        if (stream.getframerate(), stream.getnchannels(), stream.getsampwidth()) != (16000, 1, 2):
            raise ValueError("benchmark requires normalized 16kHz mono PCM16")
        pcm = stream.readframes(stream.getnframes())
    if not pcm:
        raise ValueError("empty synthesized fixture")
    return bytes(pcm)


def main() -> None:
    layout = RuntimeLayout()
    layout.configure()
    sources = {
        "it": ("italian.wav", "Tobi memorizza questo come il mio zaino"),
        "en": ("english.wav", "Tobi remember this as my backpack"),
    }
    fixtures = {
        language: (read_pcm(layout.path("datasets/speech-synthetic/" + name)), expected)
        for language, (name, expected) in sources.items()
    }
    results = []
    for model in ["whisper-tiny", "whisper-base"]:
        for gpu in [False, True]:
            provider = WhisperASR(model=model, gpu=gpu)
            metrics = Metrics()
            scores = {}
            try:
                for language, (pcm, expected) in fixtures.items():
                    for iteration in range(4):
                        start = time.perf_counter()
                        segments = provider.transcribe(pcm, language)
                        elapsed = (time.perf_counter() - start) * 1000
                        metrics.observe(
                            language + ("_first" if iteration == 0 else "_warm"), elapsed
                        )
                        scores[language] = word_error_rate(
                            expected, " ".join(s.text for s in segments)
                        )
            finally:
                provider.unload()
            results.append(
                {
                    "model": model,
                    "backend": "metal" if gpu else "cpu",
                    "wer": scores,
                    "metrics": metrics.report(),
                }
            )
    vad = SileroVAD()
    metrics = Metrics()
    positive = {}
    try:
        for language, (pcm, _) in fixtures.items():
            vad.reset()
            probabilities = []
            for offset in range(0, len(pcm) - 1023, 1024):
                with metrics.measure("vad_window_32ms"):
                    probabilities.append(vad.probability(pcm[offset : offset + 1024]))
            positive[language] = sum(p >= 0.6 for p in probabilities)
        vad.reset()
        assert all(vad.probability(bytes(1024)) < 0.35 for _ in range(20))
    finally:
        vad.unload()
    result = {
        "scope": "two synthetic voice fixtures; not representative real-world WER",
        "asr": results,
        "vad": metrics.report(),
        "voiced_windows": positive,
        "fixture_sha256": {
            lang: hashlib.sha256(pcm).hexdigest() for lang, (pcm, _) in fixtures.items()
        },
        "process_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    layout.path("exports/speech-benchmark.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
