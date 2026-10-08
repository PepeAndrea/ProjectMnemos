"""Real isolated HTTP failure/recovery over simulated drivers; never native sensors."""

import asyncio
import importlib
import json
import socket
import tempfile
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import uvicorn

from .api import create_app
from .capture import CaptureSession
from .media import MediaFailureCode, MediaSourceFailure, VideoFrame
from .runtime import RuntimeLayout
from .storage import EntityRepository
from .vision import Detection


class EmptyDetector:
    def detect(self, frame: VideoFrame) -> list[Detection]:
        return []

    def unload(self) -> None:
        pass


class FaultSource:
    def __init__(self, gate: threading.Event, *, failed: bool):
        self.gate, self.failed = gate, failed
        self.closed = False

    def frames(self) -> Iterator[VideoFrame]:
        if self.failed:
            raise MediaSourceFailure(MediaFailureCode.CAMERA_OPEN)
        sequence = 0
        while not self.closed:
            yield VideoFrame(
                "synthetic-recovery",
                sequence,
                time.monotonic() + 0.1,
                datetime.now(UTC),
                32,
                32,
                "bgr24",
                bytes([30, 90, 40]) * 1024,
            )
            sequence += 1

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self.failed and not self.gate.wait(15):
            raise TimeoutError("synthetic fixture cleanup gate timed out")


def main() -> None:
    layout = RuntimeLayout()
    layout.configure()
    token = "synthetic-source-failure-token-only-123456789"
    gate = threading.Event()
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    server = None
    worker = None
    with tempfile.TemporaryDirectory(
        prefix="source-failure-http-", dir=layout.path("tmp")
    ) as folder:
        root = RuntimeLayout(Path(folder))
        repo = EntityRepository("sqlite:///" + str(Path(folder) / "fixture.db"))
        repo.initialize()
        captures: list[CaptureSession] = []

        def factory(mode: str, *args: Any, **kwargs: Any) -> CaptureSession:
            if mode != "replay":
                raise PermissionError("synthetic-only verifier; native modes disabled")
            capture = CaptureSession(
                FaultSource(gate, failed=not captures), None, EmptyDetector(), EmptyDetector()
            )
            captures.append(capture)
            return capture

        app = create_app(repo, token, root, capture_factory=factory)
        server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", access_log=False)
        )
        worker = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        try:
            worker.start()
            deadline = time.monotonic() + 5
            while not server.started:
                if not worker.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("synthetic HTTP startup failed")
                time.sleep(0.01)

            def call(
                method: str,
                route: str,
                body: dict[str, Any] | None = None,
                *,
                authenticated: bool = True,
            ) -> Any:
                headers = {"Content-Type": "application/json"}
                if authenticated:
                    headers["Authorization"] = "Bearer " + token
                req = Request(
                    f"http://127.0.0.1:{port}{route}",
                    data=json.dumps(body).encode() if body else None,
                    headers=headers,
                    method=method,
                )
                with urlopen(req, timeout=8) as response:
                    return response.read() if route == "/capture/frame" else json.load(response)

            try:
                call("GET", "/capture/status", authenticated=False)
            except HTTPError as exc:
                assert exc.code == 401
            else:
                raise AssertionError("owner auth missing")
            body = {"mode": "replay", "camera": True, "microphone": False}
            call("POST", "/capture/start", body)
            deadline = time.monotonic() + 3
            while True:
                failed = call("GET", "/capture/status")
                if failed["state"] == "failed":
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError("failure status missing")
                time.sleep(0.01)
            assert failed["error_code"] == "camera-open-failed" and failed["worker_active"]
            assert not failed["tracks"] and not failed["video_buffer_bytes"]
            try:
                call("POST", "/capture/start", body)
            except HTTPError as exc:
                assert exc.code == 409
            else:
                raise AssertionError("second source opened while failed worker live")
            assert len(captures) == 1
            before = time.perf_counter()
            gate.set()
            deadline = time.monotonic() + 3
            while call("GET", "/capture/status")["worker_active"]:
                if time.monotonic() > deadline:
                    raise RuntimeError("failed worker cleanup incomplete")
                time.sleep(0.01)
            cleanup_ms = (time.perf_counter() - before) * 1000
            assert call("GET", "/capture/status")["error_code"] == "camera-open-failed"
            recovered = call("POST", "/capture/start", body)
            assert recovered["id"] != failed["id"] and recovered["error_code"] is None
            deadline = time.monotonic() + 3
            while not call("GET", "/capture/status")["processed_frames"]:
                if time.monotonic() > deadline:
                    raise RuntimeError("explicit recovery missing preview")
                time.sleep(0.01)
            assert call("GET", "/capture/frame")[:2] == b"\xff\xd8"
            stopped = call("POST", "/capture/stop")
            assert stopped["state"] == "stopped" and not stopped["worker_active"]
            assert stopped["error_code"] is None and not stopped["video_buffer_bytes"]
            report = {
                "passed": True,
                "scope": "real isolated HTTP/SQLite; simulated camera-open failure and generated recovery pixels, no native sensor or OS permission",
                "owner_auth": True,
                "failed_worker_blocks_restart": True,
                "first_error_preserved": True,
                "cleanup_after_gate_release_ms": cleanup_ms,
                "explicit_restart_preview": True,
                "stop_cleared_media": True,
            }
        finally:
            gate.set()
            server.should_exit = True
            worker.join(timeout=5)
            listener.close()
            repo.close()
            if worker.is_alive():
                raise RuntimeError("synthetic HTTP server cleanup incomplete")
    layout.path("exports/source-failure-http.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


def benchmark() -> None:
    # Warm the shared media dependency before measuring worker scheduling/cleanup.
    importlib.import_module("cv2")
    importlib.import_module("numpy")
    gate = threading.Event()
    gate.set()
    timings = []

    async def repeat() -> None:
        for _ in range(50):
            capture = CaptureSession(
                FaultSource(gate, failed=True), None, EmptyDetector(), EmptyDetector()
            )
            start = time.perf_counter()
            capture.start()
            assert capture.task is not None
            await capture.task
            timings.append((time.perf_counter() - start) * 1000)
            assert (
                capture.error_code == "camera-open-failed"
                and not capture.snapshot()["worker_active"]
            )

    asyncio.run(repeat())
    report = {
        "passed": True,
        "scope": "50 simulated open faults, warm media dependencies, worker scheduling/cleanup only; no native device timing",
        "p50_ms": sorted(timings)[24],
        "p95_ms": sorted(timings)[47],
    }
    layout = RuntimeLayout()
    layout.configure()
    layout.path("exports/source-failure-benchmark.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
    benchmark()
