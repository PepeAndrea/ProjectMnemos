"""Generate non-private local speech fixtures; no microphone or audible playback."""

import hashlib
import json
import platform
import subprocess
import wave

from .runtime import RuntimeLayout
from .speech_benchmark import read_pcm


def main() -> None:
    if platform.system() != "Darwin":
        raise RuntimeError("fixture generation uses existing macOS speech voices")
    layout = RuntimeLayout()
    layout.configure()
    directory = layout.path("datasets/speech-synthetic")
    directory.mkdir(parents=True, exist_ok=True)
    records = []
    for name, language, voice, text in [
        ("italian", "it", "Alice", "Tobi, memorizza questo come il mio zaino."),
        ("english", "en", "Samantha", "Tobi, remember this as my backpack."),
    ]:
        temporary = layout.path("tmp/speech-" + name + ".aiff")
        output = directory / (name + ".wav")
        subprocess.run(
            ["/usr/bin/say", "-v", voice, "-o", str(temporary), text], check=True, timeout=30
        )
        subprocess.run(
            ["/usr/bin/afconvert", "-f", "WAVE", "-d", "LEI16@16000", str(temporary), str(output)],
            check=True,
            timeout=30,
        )
        pcm = read_pcm(output)
        temporary.unlink(missing_ok=True)
        records.append(
            {
                "filename": output.name,
                "language": language,
                "voice": voice,
                "reference_text": text,
                "duration_seconds": len(pcm) / 32000,
                "pcm_sha256": hashlib.sha256(pcm).hexdigest(),
                "wav_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            }
        )
    # A longer silent tail makes completed text observable during paced capture verification.
    with wave.open(str(directory / "stream.wav"), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(read_pcm(directory / "english.wav") + bytes(16000 * 2 * 3))
    with wave.open(str(directory / "stream-it.wav"), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(read_pcm(directory / "italian.wav") + bytes(16000 * 2 * 3))
    (directory / "source.json").write_text(
        json.dumps(
            {
                "source": "local macOS synthetic speech; not a recording of a real person",
                "os": platform.platform(),
                "fixtures": records,
                "redistribution": "not committed or redistributed; regenerate with installed voices",
            },
            indent=2,
        )
        + "\n"
    )
    print("two synthetic voice fixtures generated under runtime/datasets/speech-synthetic")


if __name__ == "__main__":
    main()
