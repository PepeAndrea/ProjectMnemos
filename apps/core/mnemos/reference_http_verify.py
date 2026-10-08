"""Live loopback HTTP/PostgreSQL synthetic reference flow; never opens a device."""

import importlib
import json
import socket
import tempfile
import threading
import time
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

import uvicorn
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from . import api
from .capture import CaptureSession
from .media import VideoFrame
from .runtime import RuntimeLayout
from .storage import EntityRepository, LocalActionRow
from .vision import Box, Detection


class SyntheticVideo:
    def __init__(self) -> None:
        self.closed = False
        self.pixels = bytes([20, 90, 40]) * (128 * 128)

    def frames(self) -> Iterator[VideoFrame]:
        sequence = 0
        while not self.closed:
            yield VideoFrame(
                "synthetic-reference-http",
                sequence,
                time.monotonic() + 0.1,
                datetime.now(UTC),
                128,
                128,
                "bgr24",
                self.pixels,
            )
            sequence += 1

    def close(self) -> None:
        self.closed = True


class SyntheticDetector:
    def __init__(self, empty: bool = False):
        self.empty = empty

    def detect(self, frame: VideoFrame) -> list[Detection]:
        return (
            []
            if self.empty
            else [Detection("backpack", 0.9, Box(16, 16, 96, 96), frame.source_id, frame.sequence)]
        )

    def unload(self) -> None:
        pass


def build(mode: str, *args: Any, **kwargs: Any) -> CaptureSession:
    if mode != "replay":
        raise PermissionError("synthetic-only verification; native modes disabled")
    return CaptureSession(SyntheticVideo(), None, SyntheticDetector(), SyntheticDetector(True))


def main() -> None:
    layout = RuntimeLayout()
    layout.configure()
    repo = EntityRepository("postgresql+psycopg://mnemos:mnemos@127.0.0.1:5432/mnemos")
    original = repo.engine
    schema = "test_reference_http_" + uuid4().hex
    with original.begin() as connection:
        connection.execute(CreateSchema(schema))
    repo.engine = original.execution_options(schema_translate_map={None: schema})
    token = "synthetic-reference-http-token-only-123456789"
    server: uvicorn.Server | None = None
    worker: threading.Thread | None = None
    listener: socket.socket | None = None
    try:
        repo.initialize()
        with tempfile.TemporaryDirectory(
            prefix="reference-http-", dir=layout.path("tmp")
        ) as folder:
            local = RuntimeLayout(Path(folder))
            sources: list[SyntheticVideo] = []

            def multi_view_build(mode: str, *args: Any, **kwargs: Any) -> CaptureSession:
                if mode != "replay":
                    raise PermissionError("synthetic-only verification; native modes disabled")
                source = SyntheticVideo()
                sources.append(source)
                return CaptureSession(source, None, SyntheticDetector(), SyntheticDetector(True))

            app = api.create_app(repo, token, local, capture_factory=multi_view_build)
            listener = socket.socket()
            listener.bind(("127.0.0.1", 0))
            listener.listen(128)
            port = listener.getsockname()[1]
            server = uvicorn.Server(
                uvicorn.Config(
                    app, host="127.0.0.1", port=port, log_level="error", access_log=False
                )
            )
            worker = threading.Thread(
                target=server.run, kwargs={"sockets": [listener]}, daemon=True
            )
            worker.start()
            base = f"http://127.0.0.1:{port}"

            def call(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
                request = Request(
                    base + path,
                    method=method,
                    headers={
                        "Authorization": "Bearer " + token,
                        "Content-Type": "application/json",
                    },
                    data=json.dumps(body).encode() if body is not None else None,
                )
                with urlopen(request, timeout=10) as response:
                    if path.endswith("/image"):
                        assert response.headers["Cache-Control"] == "no-store"
                        return response.read()
                    return json.load(response)

            deadline = time.monotonic() + 5
            while not server.started:
                if time.monotonic() > deadline:
                    raise RuntimeError("isolated HTTP server startup timeout")
                time.sleep(0.02)
            entity = call(
                "POST",
                "/entities",
                {
                    "kind": "object",
                    "name": "Synthetic HTTP reference " + uuid4().hex,
                    "enrolled": True,
                    "confidence": 1,
                    "provenance": {"source_id": "synthetic-http", "method": "human"},
                    "retention": {
                        "scope": "persistent",
                        "purpose": "explicit synthetic verification",
                    },
                },
            )
            capture = call("POST", "/capture/start", {"mode": "replay", "microphone": False})
            deadline = time.monotonic() + 5
            while True:
                status = call("GET", "/capture/status")
                if status["tracks"]:
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError("synthetic track unavailable")
                time.sleep(0.02)
            track = status["tracks"][0]["track_id"]
            path = f"/capture/{capture['id']}/tracks/{track}"
            assert call(
                "POST", path + "/bind", {"entity_id": entity["id"], "confirm_observed_object": True}
            )["bound"]
            before = time.perf_counter()
            result = call(
                "POST",
                path + "/reference",
                {
                    "entity_id": entity["id"],
                    "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                    "confirm_object_only_reference": True,
                },
            )
            save_ms = (time.perf_counter() - before) * 1000
            key = result["id"]
            listing = call("GET", f"/objects/{entity['id']}/references")
            assert [row["id"] for row in listing] == [key]
            assert listing[0]["quality"]["warnings"] == ["low-contrast", "low-edge-detail"]
            assert "content_tag" not in listing[0]
            jpeg = call("GET", f"/references/{key}/image")
            cv, np = importlib.import_module("cv2"), importlib.import_module("numpy")
            decoded = cv.imdecode(np.frombuffer(jpeg, np.uint8), cv.IMREAD_COLOR)
            assert decoded.shape[:2] == (96, 96), "reference must contain crop, not full frame"
            encrypted = local.path(f"media/evidence/object-references/{key}.enc")
            assert encrypted.exists() and encrypted.read_bytes() != jpeg
            assert encrypted.stat().st_mode & 0o777 == 0o600
            body = {
                "entity_id": entity["id"],
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                "confirm_object_only_reference": True,
            }
            try:
                call("POST", path + "/reference", body)
            except HTTPError as error:
                assert error.code == 422
            else:
                raise AssertionError("duplicate reference should request another view")

            def replace_pixels(pixels: bytes) -> None:
                sequence = call("GET", "/capture/status")["tracks"][0]["sequence"]
                sources[0].pixels = pixels
                until = time.monotonic() + 3
                while call("GET", "/capture/status")["tracks"][0]["sequence"] <= sequence + 2:
                    if time.monotonic() > until:
                        raise RuntimeError("synthetic replacement frame did not arrive")
                    time.sleep(0.02)

            replace_pixels(bytes(128 * 128 * 3))
            try:
                call("POST", path + "/reference", body)
            except HTTPError as error:
                assert error.code == 422
            else:
                raise AssertionError("no-signal reference should reject before persistence")
            assert len(call("GET", f"/objects/{entity['id']}/references")) == 1
            checker = ((np.indices((128, 128)).sum(axis=0) // 8) % 2 * 180 + 35).astype(np.uint8)
            replace_pixels(np.repeat(checker[:, :, None], 3, axis=2).tobytes())
            second = call("POST", path + "/reference", body)["id"]
            second_jpeg = call("GET", f"/references/{second}/image")
            assert jpeg != second_jpeg
            listing = call("GET", f"/objects/{entity['id']}/references")
            assert {row["id"] for row in listing} == {key, second}
            assert next(row for row in listing if row["id"] == second)["quality"]["warnings"] == []
            call("POST", "/capture/stop")
            stopped = call("GET", "/capture/status")
            assert stopped["tracks"] == []
            assert call("GET", f"/references/{key}/image") == jpeg
            before = time.perf_counter()
            call(
                "POST",
                f"/references/{key}/delete",
                {"confirmed_name": entity["name"], "confirm_irreversible": True},
            )
            try:
                call("GET", f"/references/{key}/image")
            except HTTPError as error:
                assert error.code in (403, 404)
            else:
                raise AssertionError("revoked reference remained readable")
            assert [row["id"] for row in call("GET", f"/objects/{entity['id']}/references")] == [
                second
            ]
            assert call("GET", f"/references/{second}/image") == second_jpeg
            call(
                "POST",
                f"/references/{second}/delete",
                {"confirmed_name": entity["name"], "confirm_irreversible": True},
            )
            assert call("GET", f"/objects/{entity['id']}/references") == []
            deadline = time.monotonic() + 3
            while (
                encrypted.exists()
                or local.path(f"media/evidence/object-references/{second}.enc").exists()
            ):
                if time.monotonic() > deadline:
                    raise RuntimeError("physical cleanup did not finish")
                time.sleep(0.05)
            delete_ms = (time.perf_counter() - before) * 1000
            with Session(repo.engine) as session:
                audits = list(session.scalars(select(LocalActionRow)))
                kinds = Counter(row.payload["result"]["proposal"]["kind"] for row in audits)
                assert kinds["reference_store"] == kinds["reference_delete"] == 2
                assert kinds["reference_read"] >= 2
                assert all(entity["name"] not in json.dumps(row.payload) for row in audits)
            report = {
                "passed": True,
                "scope": "live loopback HTTP, isolated PostgreSQL schema, generated pixels/detections; no sensor or recognition accuracy claim",
                "save_ms": save_ms,
                "delete_cleanup_ms": delete_ms,
                "crop_dimensions": [96, 96],
                "encrypted_file_private": True,
                "persisted_after_stop": True,
                "revoked_read_denied": True,
                "audit_kinds": dict(kinds),
                "distinct_synthetic_views": 2,
                "quality_warnings_visible": True,
                "duplicate_rejected": True,
                "no_signal_rejected": True,
                "other_view_survived_first_revocation": True,
            }
            server.should_exit = True
            worker.join(timeout=5)
            if worker.is_alive():
                raise RuntimeError("isolated server shutdown incomplete")
    finally:
        if server:
            server.should_exit = True
        if worker:
            worker.join(timeout=5)
        if listener:
            listener.close()
        with original.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        repo.close()
    layout.path("exports/reference-http.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
