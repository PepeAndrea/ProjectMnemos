"""Temporary display annotations: never biometric identity or speaker authority."""

import math
import re
import time
from typing import Any

from .speech_stream import TranscriptUpdate

INTRODUCTION = re.compile(
    r"^(?:(?:tobi|toby)\s*[,.:!?-]?\s*)?"
    r"(?:mi chiamo|my name is|questa persona si chiama|this person is called)\s+"
    r"([\wÀ-ÿ][\wÀ-ÿ '\-]{0,79})[.!?]?$",
    re.IGNORECASE,
)


def introduced_name(text: str) -> str | None:
    if len(text) > 256:
        return None
    match = INTRODUCTION.fullmatch(text.strip())
    if match is None:
        return None
    name = match.group(1).strip()
    # Do not consume clauses or commands as names; this is intentionally a small grammar.
    if len(name.split()) > 4 or any(
        word.casefold() in {"e", "and", "poi", "then", "non", "not"} for word in name.split()
    ):
        return None
    return name or None


class SessionNames:
    def __init__(self) -> None:
        self.labels: dict[str, dict[str, Any]] = {}
        self.seen: dict[str, float] = {}
        self.sole_face: str | None = None
        self.sole_since = 0.0
        self.last_observed = 0.0

    def prune(self, tracks: dict[str, dict[str, Any]], observed: float) -> None:
        at = time.monotonic()
        self.labels = {
            key: value
            for key, value in self.labels.items()
            if key in tracks and 0 <= at - observed <= 2
        }
        self.seen = {key: until for key, until in self.seen.items() if until > at}

    def observe(self, tracks: dict[str, dict[str, Any]], observed: float) -> None:
        faces = [key for key, row in tracks.items() if row["label"] == "face"]
        key = faces[0] if len(faces) == 1 else None
        if key != self.sole_face or observed - self.last_observed > 2:
            self.sole_face, self.sole_since = key, observed
        self.last_observed = observed
        self.prune(tracks, observed)

    def assign(
        self, track_id: str, name: str, tracks: dict[str, dict[str, Any]], observed: float
    ) -> None:
        self.prune(tracks, observed)
        if track_id not in tracks or not 0 <= time.monotonic() - observed <= 2:
            raise KeyError("track unavailable")
        if tracks[track_id]["label"] != "face":
            raise ValueError("select a visible face track")
        if not name.strip() or len(name.strip()) > 80:
            raise ValueError("name must contain 1 to 80 characters")
        self.labels[track_id] = {
            "name": name.strip(),
            "source": "owner-panel",
            "verified_identity": False,
        }

    def offer(
        self, update: TranscriptUpdate, tracks: dict[str, dict[str, Any]], observed: float
    ) -> None:
        self.prune(tracks, observed)
        at = time.monotonic()
        if (
            update.partial
            or update.id in self.seen
            or not math.isfinite(update.confidence)
            or not 0.8 <= update.confidence <= 1
            or not math.isfinite(update.start_seconds)
            or not math.isfinite(update.end_seconds)
            or not at - 5 <= update.start_seconds <= update.end_seconds <= at + 1
        ):
            return
        self.seen[update.id] = at + 300
        while len(self.seen) > 200:
            del self.seen[next(iter(self.seen))]
        name = introduced_name(update.text)
        faces = [key for key, row in tracks.items() if row["label"] == "face"]
        # Only contemporaneous single-face context; even then the label is unverified.
        if (
            name is None
            or len(faces) != 1
            or self.sole_face != faces[0]
            or self.sole_since > update.start_seconds
            or not update.start_seconds <= observed <= update.end_seconds + 1
        ):
            return
        key = faces[0]
        if key not in self.labels:  # Audio never overwrites an owner correction or earlier label.
            self.labels[key] = {
                "name": name,
                "source": "anonymous-audio",
                "verified_identity": False,
            }

    def clear(self) -> None:
        self.labels.clear()
        self.seen.clear()
        self.sole_face = None
        self.sole_since = self.last_observed = 0.0
