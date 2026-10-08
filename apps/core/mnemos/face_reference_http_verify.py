"""Real isolated HTTP/PostgreSQL flow over generated pixels, never real faces/sensors."""

import json
import socket
import tempfile
import threading
import time
from collections import Counter
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

from .api import create_app
from .capture import CaptureSession
from .media import VideoFrame
from .reference_http_verify import SyntheticVideo
from .runtime import RuntimeLayout
from .storage import EntityRepository, LocalActionRow
from .vision import Box, Detection


class Detector:
    def __init__(self, face: bool):
        self.face = face

    def detect(self, frame: VideoFrame) -> list[Detection]:
        return (
            [
                Detection(
                    "face",
                    0.9,
                    Box(16, 16, 96, 96),
                    frame.source_id,
                    frame.sequence,
                    ((40.0, 48.0), (88.0, 48.0), (64.0, 72.0), (48.0, 92.0), (80.0, 92.0)),
                )
            ]
            if self.face
            else []
        )

    def unload(self) -> None:
        pass


def main() -> None:
    layout = RuntimeLayout()
    layout.configure()
    repo = EntityRepository("postgresql+psycopg://mnemos:mnemos@127.0.0.1:5432/mnemos")
    original = repo.engine
    schema = "test_face_http_" + uuid4().hex
    with original.begin() as connection:
        connection.execute(CreateSchema(schema))
    repo.engine = original.execution_options(schema_translate_map={None: schema})
    server = None
    worker = None
    listener = None
    try:
        repo.initialize()
        with tempfile.TemporaryDirectory(prefix="face-http-", dir=layout.path("tmp")) as folder:
            local = RuntimeLayout(Path(folder))
            source = SyntheticVideo()

            def factory(mode: str, *args: Any, **kwargs: Any) -> CaptureSession:
                if mode != "replay":
                    raise PermissionError("synthetic-only verification; native sensors disabled")
                return CaptureSession(source, None, Detector(False), Detector(True))

            token = "synthetic-face-http-token-only-123456789"
            app = create_app(repo, token, local, capture_factory=factory)
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

            def call(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
                request = Request(
                    f"http://127.0.0.1:{port}" + path,
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

            until = time.monotonic() + 5
            while not server.started:
                if time.monotonic() > until:
                    raise RuntimeError("synthetic HTTP startup timeout")
                time.sleep(0.02)
            person = call(
                "POST",
                "/people",
                {
                    "name": "Synthetic face HTTP " + uuid4().hex,
                    "face": True,
                    "voice": False,
                    "subject_permission_attested": True,
                    "expires_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
                },
            )
            capture = call("POST", "/capture/start", {"mode": "replay", "microphone": False})
            until = time.monotonic() + 5
            while True:
                status = call("GET", "/capture/status")
                if status["tracks"]:
                    break
                if time.monotonic() > until:
                    raise RuntimeError("synthetic face track timeout")
                time.sleep(0.02)
            assert status["tracks"][0]["entity_id"] is None
            assert "landmarks" not in json.dumps(status)
            track = status["tracks"][0]["track_id"]
            path = f"/capture/{capture['id']}/faces/{track}/reference"
            body = {
                "entity_id": person["id"],
                "confirmed_name": person["name"],
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                "confirm_face_reference": True,
            }
            before = time.perf_counter()
            first = call("POST", path, body)["id"]
            save_ms = (time.perf_counter() - before) * 1000
            jpeg = call("GET", f"/face-references/{first}/image")
            encrypted = local.path(f"media/evidence/face-references/{first}.enc")
            assert encrypted.read_bytes() != jpeg and encrypted.stat().st_mode & 0o777 == 0o600
            assert not local.path("data/security/reference-key").exists()
            assert not local.path("data/security/biometric-key").exists()
            source.pixels = bytes([100, 150, 100]) * (128 * 128)
            sequence = status["tracks"][0]["sequence"]
            until = time.monotonic() + 3
            while call("GET", "/capture/status")["tracks"][0]["sequence"] <= sequence + 3:
                if time.monotonic() > until:
                    raise RuntimeError("second generated face view timeout")
                time.sleep(0.02)
            second = call("POST", path, body)["id"]
            second_jpeg = call("GET", f"/face-references/{second}/image")
            assert jpeg != second_jpeg
            listing_path = f"/people/{person['id']}/face-references"
            listing = call("GET", listing_path)
            assert len(listing) == 2
            assert all(row["quality"]["face"]["landmarks_available"] for row in listing)
            assert all(row["quality"]["face"]["eye_line_roll_degrees"] == 0 for row in listing)
            assert all(not row["quality"]["face"]["calibrated"] for row in listing)
            assert call("GET", "/capture/status")["tracks"][0]["entity_id"] is None
            call("POST", "/capture/stop")
            assert call("GET", "/capture/status")["tracks"] == []
            assert call("GET", f"/face-references/{first}/image") == jpeg
            call(
                "POST",
                f"/face-references/{first}/delete",
                {"confirmed_name": person["name"], "confirm_irreversible": True},
            )
            assert [row["id"] for row in call("GET", listing_path)] == [second]
            assert call("GET", f"/face-references/{second}/image") == second_jpeg
            before = time.perf_counter()
            call(
                "POST",
                f"/people/{person['id']}/revoke",
                {"confirmed_name": person["name"], "confirm_irreversible": True},
            )
            for key in (first, second):
                try:
                    call("GET", f"/face-references/{key}/image")
                except HTTPError as error:
                    assert error.code in (403, 404)
                else:
                    raise AssertionError("consent-revoked face remained accessible")
            until = time.monotonic() + 3
            while (
                encrypted.exists()
                or local.path(f"media/evidence/face-references/{second}.enc").exists()
            ):
                if time.monotonic() > until:
                    raise RuntimeError("face image cleanup timeout")
                time.sleep(0.05)
            cleanup_ms = (time.perf_counter() - before) * 1000
            with Session(repo.engine) as session:
                audits = list(session.scalars(select(LocalActionRow)))
                kinds = Counter(row.payload["result"]["proposal"]["kind"] for row in audits)
                assert kinds["person_enroll"] == kinds["person_revoke"] == 1
                assert kinds["reference_store"] == 2 and kinds["track_bind"] == 0
                assert all(person["name"] not in json.dumps(row.payload) for row in audits)
            report = {
                "passed": True,
                "scope": "real isolated HTTP/PostgreSQL; generated pixels/face boxes only, no real subject/sensor or recognition calibration",
                "save_ms": save_ms,
                "revoke_cleanup_ms": cleanup_ms,
                "distinct_synthetic_views": 2,
                "face_tracks_stayed_anonymous": True,
                "raw_landmarks_not_in_status": True,
                "generated_geometry_in_authorized_listing": True,
                "independent_view_revocation": True,
                "consent_revocation_denied_remaining_views": True,
                "encrypted_files_deleted": True,
                "audit_kinds": dict(kinds),
            }
            server.should_exit = True
            worker.join(timeout=5)
            if worker.is_alive():
                raise RuntimeError("synthetic server shutdown incomplete")
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
    layout.path("exports/face-reference-http.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
