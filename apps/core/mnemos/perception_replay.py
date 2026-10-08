"""Actual ONNX detector/face/tracker replay over a public-domain test fixture."""

import hashlib
import importlib
import json

from .media import OpenCVVideoSource, SourceClock, WaveAudioSource
from .metrics import Metrics
from .replay import replay
from .runtime import ROOT, RuntimeLayout
from .tracking import SessionTracker
from .vision import YOLOXProvider, YuNetProvider


def main() -> None:
    layout = RuntimeLayout()
    layout.configure()
    metadata = json.loads(layout.path("datasets/public/astronaut-source.json").read_text())
    image_path = layout.path("datasets/public/astronaut.png")
    if hashlib.sha256(image_path.read_bytes()).hexdigest() != metadata["sha256"]:
        raise ValueError("replay fixture checksum mismatch")
    cv, np = importlib.import_module("cv2"), importlib.import_module("numpy")
    image = cv.imread(str(image_path))
    output = layout.path("datasets/perception-replay")
    output.mkdir(parents=True, exist_ok=True)
    replay(ROOT / "tests/fixtures/scenario.json", output)
    writer = cv.VideoWriter(
        str(output / "replay.avi"), cv.VideoWriter_fourcc(*"MJPG"), 1.0, (512, 512)
    )
    if not writer.isOpened():
        raise OSError("replay video writer unavailable")
    try:
        for pixels in [image, image, np.zeros_like(image), image]:
            writer.write(pixels)
    finally:
        writer.release()
    clock = SourceClock()
    source = OpenCVVideoSource(output / "replay.avi", clock=clock)
    audio = WaveAudioSource(output / "tone.wav", clock=clock)
    detector, face = YOLOXProvider(), YuNetProvider()
    tracker = SessionTracker(max_missed=0)
    metrics = Metrics()
    lifecycle: list[str] = []
    face_counts = []
    first_video_time = None
    try:
        for frame in source.frames():
            if first_video_time is None:
                first_video_time = frame.monotonic_seconds
            with metrics.measure("detection"):
                detections = detector.detect(frame)
            with metrics.measure("face"):
                faces = face.detect(frame)
            face_counts.append(len(faces))
            lifecycle.extend(
                update.kind
                for update in tracker.update(detections, frame.source_id, frame.sequence)
            )
        chunks = list(audio.chunks())
        assert chunks[0].monotonic_seconds == first_video_time
        assert len(chunks) == 200
        assert lifecycle == ["enter", "update", "exit", "enter"], lifecycle
        assert face_counts == [1, 1, 0, 1], face_counts
    finally:
        source.close()
        audio.close()
        detector.unload()
        face.unload()
        tracker.clear()
    result = {
        "passed": True,
        "scope": "one public-domain person fixture and black negatives; not calibrated accuracy",
        "lifecycle": lifecycle,
        "face_counts": face_counts,
        "audio_chunks": len(chunks),
        "metrics": metrics.report(),
        "fixture_sha256": metadata["sha256"],
    }
    path = layout.path("exports/perception-replay.json")
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
