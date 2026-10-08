"""Bounded anonymous session tracking. No cross-session physical identity claims."""

from dataclasses import dataclass
from uuid import uuid4

from .vision import Box, Detection


def iou(a: Box, b: Box) -> float:
    intersection = max(0.0, min(a.x + a.width, b.x + b.width) - max(a.x, b.x)) * max(
        0.0, min(a.y + a.height, b.y + b.height) - max(a.y, b.y)
    )
    union = a.width * a.height + b.width * b.height - intersection
    return intersection / union if union > 0 else 0.0


@dataclass
class Track:
    id: str
    detection: Detection
    misses: int = 0


@dataclass(frozen=True)
class TrackUpdate:
    kind: str
    track_id: str
    detection: Detection


class SessionTracker:
    def __init__(self, threshold: float = 0.4, max_missed: int = 2, capacity: int = 128):
        if not 0 < threshold <= 1 or max_missed < 0 or capacity < 1:
            raise ValueError("invalid tracker configuration")
        self.threshold, self.max_missed, self.capacity = threshold, max_missed, capacity
        self.tracks: dict[str, Track] = {}
        self.source_id: str | None = None
        self.last_sequence = -1
        self.dropped = 0

    def update(
        self, detections: list[Detection], source_id: str, sequence: int
    ) -> list[TrackUpdate]:
        if self.source_id not in {None, source_id} or sequence <= self.last_sequence:
            raise ValueError("tracker requires one ordered source session")
        if any(d.source_id != source_id or d.sequence != sequence for d in detections):
            raise ValueError("detection source/sequence mismatch")
        self.source_id, self.last_sequence = source_id, sequence
        updates: list[TrackUpdate] = []
        matched: set[str] = set()
        existing = set(self.tracks)
        for detection in detections:
            candidates = sorted(
                [
                    (iou(detection.box, track.detection.box), key)
                    for key, track in self.tracks.items()
                    if key in existing
                    and key not in matched
                    and track.detection.label == detection.label
                ],
                reverse=True,
            )
            if (
                candidates
                and candidates[0][0] >= self.threshold
                and (len(candidates) == 1 or candidates[0][0] - candidates[1][0] >= 0.1)
            ):
                key = candidates[0][1]
                track = self.tracks[key]
                track.detection, track.misses = detection, 0
                matched.add(key)
                updates.append(TrackUpdate("update", key, detection))
            else:
                if len(self.tracks) >= self.capacity:
                    self.dropped += 1
                    continue
                track = Track(str(uuid4()), detection)
                self.tracks[track.id] = track
                matched.add(track.id)
                updates.append(TrackUpdate("enter", track.id, detection))
        for key in existing - matched:
            track = self.tracks[key]
            track.misses += 1
            if track.misses > self.max_missed:
                updates.append(TrackUpdate("exit", key, track.detection))
                del self.tracks[key]
        return updates

    def clear(self) -> None:
        self.tracks.clear()
        self.source_id = None
        self.last_sequence = -1
