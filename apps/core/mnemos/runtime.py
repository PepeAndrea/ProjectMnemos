"""Resource containment and bounded volatile media state."""

import asyncio
import math
import os
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar

T = TypeVar("T")
ROOT = Path(__file__).resolve().parents[3]


class RuntimeLayout:
    def __init__(self, root: Path = ROOT):
        self.root = root.resolve()
        self.runtime = self.root / "runtime"

    def path(self, relative: str) -> Path:
        path = (self.runtime / relative).resolve()
        if not path.is_relative_to(self.runtime.resolve()) or path == self.runtime.resolve():
            raise ValueError("runtime path escapes containment")
        return path

    def configure(self) -> None:
        mappings = {
            "HF_HOME": "cache/huggingface",
            "TORCH_HOME": "cache/torch",
            "XDG_CACHE_HOME": "cache",
            "TMPDIR": "tmp",
            "UV_CACHE_DIR": "cache/uv",
        }
        for env, relative in mappings.items():
            path = self.path(relative)
            path.mkdir(parents=True, exist_ok=True)
            os.environ[env] = str(path)


class BoundedQueue(Generic[T]):
    """Latest-media-wins queue; consumers must call task_done."""

    def __init__(self, capacity: int = 4):
        if capacity < 1:
            raise ValueError("positive capacity required")
        self.queue: asyncio.Queue[T] = asyncio.Queue(capacity)
        self.dropped = 0

    def put(self, item: T) -> None:
        if self.queue.full():
            self.queue.get_nowait()
            self.queue.task_done()
            self.dropped += 1
        self.queue.put_nowait(item)


@dataclass(frozen=True)
class MediaChunk:
    timestamp: float
    payload: bytes


class RollingBuffer:
    """No filesystem IO. Both age and bytes bounded, including video."""

    def __init__(
        self, seconds: float = 300, max_bytes: int = 32 * 1024 * 1024, max_chunks: int = 20000
    ):
        if not 0 < seconds <= 300 or max_bytes <= 0 or max_chunks <= 0:
            raise ValueError("invalid buffer budget")
        self.seconds = seconds
        self.max_bytes = max_bytes
        self.max_chunks = max_chunks
        self.chunks: deque[MediaChunk] = deque()
        self.bytes_used = 0
        self.latest = float("-inf")

    def append(self, chunk: MediaChunk) -> None:
        if not math.isfinite(chunk.timestamp) or chunk.timestamp < self.latest:
            raise ValueError("non-monotonic media clock")
        self.latest = chunk.timestamp
        self.expire(chunk.timestamp)
        if not chunk.payload or len(chunk.payload) > self.max_bytes:
            return
        self.chunks.append(chunk)
        self.bytes_used += len(chunk.payload)
        while self.bytes_used > self.max_bytes or len(self.chunks) > self.max_chunks:
            self.bytes_used -= len(self.chunks.popleft().payload)

    def expire(self, at: float) -> None:
        """Evict against the source clock even when no new media arrives."""
        if not math.isfinite(at):
            raise ValueError("invalid expiration clock")
        while self.chunks and self.chunks[0].timestamp < at - self.seconds:
            self.bytes_used -= len(self.chunks.popleft().payload)

    def extract(self, start: float, end: float) -> list[MediaChunk]:
        if start > end:
            raise ValueError("invalid extraction interval")
        return [c for c in self.chunks if start <= c.timestamp <= end]

    def clear(self) -> None:
        self.chunks.clear()
        self.bytes_used = 0
        self.latest = float("-inf")
