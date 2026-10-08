"""Provider-backed vision. Unknown faces are detections, never enrolled identities."""

import importlib
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from .media import VideoFrame
from .model_inventory import model_record


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    box: Box
    source_id: str
    sequence: int
    landmarks: tuple[tuple[float, float], ...] = ()

    def public_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("landmarks")
        return payload


class DetectorProvider(Protocol):
    def detect(self, frame: VideoFrame) -> list[Detection]: ...
    def unload(self) -> None: ...


class YuNetProvider:
    def __init__(self, confidence: float = 0.8):
        if not 0 < confidence < 1:
            raise ValueError("invalid threshold")
        self.confidence = confidence
        self.model: Any = None

    def detect(self, frame: VideoFrame) -> list[Detection]:
        if frame.pixel_format != "bgr24":
            raise ValueError("YuNet requires BGR24")
        cv, np = importlib.import_module("cv2"), importlib.import_module("numpy")
        pixels = np.frombuffer(frame.pixels, dtype=np.uint8).reshape(frame.height, frame.width, 3)
        if self.model is None:
            record = model_record("yunet")
            self.model = cv.FaceDetectorYN.create(
                str(record["path"]),
                "",
                (frame.width, frame.height),
                score_threshold=self.confidence,
                top_k=500,
            )
        self.model.setInputSize((frame.width, frame.height))
        _, faces = self.model.detect(pixels)
        if faces is None:
            return []
        if faces.ndim != 2 or faces.shape[1] != 15:
            raise ValueError("unexpected YuNet landmark output schema")
        return [
            Detection(
                "face",
                float(row[-1]),
                Box(*map(float, row[:4])),
                frame.source_id,
                frame.sequence,
                tuple((float(row[index]), float(row[index + 1])) for index in range(4, 14, 2)),
            )
            for row in faces
            if np.isfinite(row).all() and row[2] > 0 and row[3] > 0
        ]

    def unload(self) -> None:
        self.model = None


class YOLOXProvider:
    def __init__(self, confidence: float = 0.4, size: int = 640):
        if not 0 < confidence < 1 or size != 640:
            raise ValueError("invalid YOLOX model configuration")
        self.confidence, self.size = confidence, size
        self.model: Any = None

    def detect(self, frame: VideoFrame) -> list[Detection]:
        if frame.pixel_format != "bgr24":
            raise ValueError("YOLOX requires BGR24")
        cv, np = importlib.import_module("cv2"), importlib.import_module("numpy")
        if self.model is None:
            record = model_record("yolox-s")
            self.model = cv.dnn.readNetFromONNX(str(record["path"]))
            self.model.setPreferableBackend(cv.dnn.DNN_BACKEND_OPENCV)
            self.model.setPreferableTarget(cv.dnn.DNN_TARGET_CPU)
        pixels = np.frombuffer(frame.pixels, dtype=np.uint8).reshape(frame.height, frame.width, 3)
        ratio = min(self.size / frame.width, self.size / frame.height)
        resized = cv.resize(pixels, (int(frame.width * ratio), int(frame.height * ratio)))
        padded = np.full((self.size, self.size, 3), 114, dtype=np.uint8)
        padded[: resized.shape[0], : resized.shape[1]] = resized
        self.model.setInput(cv.dnn.blobFromImage(padded, 1.0, (self.size, self.size), swapRB=False))
        output = self.model.forward()[0]
        grids, strides = [], []
        for stride in [8, 16, 32]:
            axis = np.arange(self.size // stride)
            x, y = np.meshgrid(axis, axis)
            grids.append(np.stack((x, y), axis=2).reshape(-1, 2))
            strides.append(np.full((len(grids[-1]), 1), stride))
        grid, scale = np.concatenate(grids), np.concatenate(strides)
        if output.shape != (len(grid), 85):
            raise ValueError("unexpected detector output schema")
        centers = (output[:, :2] + grid) * scale / ratio
        dimensions = np.exp(output[:, 2:4]) * scale / ratio
        scores = output[:, 4:5] * output[:, 5:]
        labels = np.argmax(scores, axis=1)
        confidences = np.max(scores, axis=1)
        mask = (confidences >= self.confidence) & np.isfinite(confidences)
        boxes = np.concatenate((centers - dimensions / 2, dimensions), axis=1)[mask]
        confidences, labels = confidences[mask], labels[mask]
        if not len(boxes):
            return []
        indices = cv.dnn.NMSBoxesBatched(
            boxes.tolist(), confidences.tolist(), labels.tolist(), self.confidence, 0.45
        )
        return [
            Detection(
                COCO_LABELS[int(labels[index])],
                float(confidences[index]),
                Box(*map(float, boxes[index])),
                frame.source_id,
                frame.sequence,
            )
            for index in indices
        ]

    def unload(self) -> None:
        self.model = None


COCO_LABELS = [
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "airplane",
    "bus",
    "train",
    "truck",
    "boat",
    "traffic light",
    "fire hydrant",
    "stop sign",
    "parking meter",
    "bench",
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
    "backpack",
    "umbrella",
    "handbag",
    "tie",
    "suitcase",
    "frisbee",
    "skis",
    "snowboard",
    "sports ball",
    "kite",
    "baseball bat",
    "baseball glove",
    "skateboard",
    "surfboard",
    "tennis racket",
    "bottle",
    "wine glass",
    "cup",
    "fork",
    "knife",
    "spoon",
    "bowl",
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",
    "chair",
    "couch",
    "potted plant",
    "bed",
    "dining table",
    "toilet",
    "tv",
    "laptop",
    "mouse",
    "remote",
    "keyboard",
    "cell phone",
    "microwave",
    "oven",
    "toaster",
    "sink",
    "refrigerator",
    "book",
    "clock",
    "vase",
    "scissors",
    "teddy bear",
    "hair drier",
    "toothbrush",
]
