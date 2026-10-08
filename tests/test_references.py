import os
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from mnemos.capture import CaptureSession
from mnemos.domain import Entity, Provenance, Retention
from mnemos.media import VideoFrame
from mnemos.references import ObjectReferences, ReferenceRow
from mnemos.registry import GovernedRegistry
from mnemos.runtime import RuntimeLayout
from mnemos.storage import Base, EntityRepository, LocalActionRow
from mnemos.tracking import TrackUpdate
from mnemos.vision import Box, Detection
from sqlalchemy import event, select
from sqlalchemy.orm import Session


def fixture(repo, root):
    repo.initialize()
    owner = uuid4()
    entity = GovernedRegistry(repo, owner).save(
        Entity(
            kind="object",
            name="Synthetic reference object",
            enrolled=True,
            confidence=1,
            provenance=Provenance(source_id="synthetic", method="human"),
            retention=Retention(scope="persistent", purpose="explicit enrollment"),
        )
    )
    capture = CaptureSession(object(), None)
    capture.state = "running"
    key = uuid4()
    detection = Detection("backpack", 0.9, Box(8, 8, 48, 48), "synthetic", 1)
    capture.publish_tracks([TrackUpdate("enter", str(key), detection)], time.monotonic())
    capture.reference_frame = VideoFrame(
        "synthetic",
        1,
        time.monotonic(),
        datetime.now(UTC),
        64,
        64,
        "bgr24",
        bytes([15, 80, 30]) * (64 * 64),
    )
    capture.detections = []
    claim = capture.claim_track(key)
    assert capture.finish_binding(key, entity.id, claim["claim_id"])
    jpeg, provenance = capture.object_crop(key, entity.id)
    return (
        ObjectReferences(repo, owner, RuntimeLayout(root)),
        entity,
        capture,
        key,
        jpeg,
        provenance,
    )


def test_explicit_crop_encryption_read_tamper_and_strong_delete(tmp_path):
    repo = EntityRepository("sqlite:///" + str(tmp_path / "refs.db"))
    service, entity, capture, _track, jpeg, provenance = fixture(repo, tmp_path)
    expiry = datetime.now(UTC) + timedelta(days=1)
    with pytest.raises(PermissionError):
        service.store(entity.id, jpeg, provenance, expiry, confirmed=False)
    assert not service.key.path.exists()
    key = service.store(entity.id, jpeg, provenance, expiry, confirmed=True)
    assert service.read(key) == jpeg
    assert (
        service.path(key).read_bytes() != jpeg and service.path(key).stat().st_mode & 0o777 == 0o600
    )
    assert repo.get(entity.id).reference_ids == [key]
    with pytest.raises(PermissionError):
        service.retire(key, entity.name, confirmed=False)
    with pytest.raises(PermissionError):
        service.retire(key, "wrong name", confirmed=True)
    with Session(repo.engine) as session, session.begin():
        row = session.get(ReferenceRow, str(key))
        row.payload = {**row.payload, "mime": "tampered"}
    with pytest.raises(PermissionError):
        service.read(key)
    service.retire(key, entity.name, confirmed=True)
    assert repo.get(entity.id).reference_ids == []
    with pytest.raises(PermissionError):
        service.read(key)
    assert service.cleanup() == 1 and not service.path(key).exists()
    assert service.cleanup() == 0
    capture.clear_media()
    assert capture.reference_frame is None
    with Session(repo.engine) as session:
        assert entity.name not in str(
            [row.payload for row in session.scalars(select(LocalActionRow))]
        )
    repo.close()


def test_crop_is_bound_fresh_object_only_and_does_not_persist_on_stop(tmp_path):
    repo = EntityRepository("sqlite:///" + str(tmp_path / "crop.db"))
    _, entity, capture, track, _, _ = fixture(repo, tmp_path)
    with pytest.raises(KeyError):
        capture.object_crop(track, uuid4())
    capture.detections = [{"label": "face", "box": {"x": 10, "y": 10, "width": 20, "height": 20}}]
    with pytest.raises(PermissionError):
        capture.object_crop(track, entity.id)
    capture.detections = []
    capture.reference_frame = VideoFrame(
        "mismatched", 2, time.monotonic(), datetime.now(UTC), 64, 64, "bgr24", bytes(64 * 64 * 3)
    )
    with pytest.raises(ValueError):
        capture.object_crop(track, entity.id)
    capture.last_observed = time.monotonic() - 3
    with pytest.raises(KeyError):
        capture.object_crop(track, entity.id)
    capture.clear_media()
    with pytest.raises(KeyError):
        capture.object_crop(track, entity.id)
    assert repo.get(entity.id).reference_ids == []
    repo.close()


def test_audit_failure_expiry_and_file_cleanup_retry(tmp_path, monkeypatch):
    repo = EntityRepository("sqlite:///" + str(tmp_path / "failure.db"))
    service, entity, _, _, jpeg, provenance = fixture(repo, tmp_path)

    def fail(*args):
        raise RuntimeError("synthetic audit failure")

    event.listen(LocalActionRow, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError):
            service.store(
                entity.id, jpeg, provenance, datetime.now(UTC) + timedelta(days=1), confirmed=True
            )
    finally:
        event.remove(LocalActionRow, "before_insert", fail)
    assert list(service.folder.glob("*.enc")) == [] and repo.get(entity.id).reference_ids == []
    key = service.store(
        entity.id, jpeg, provenance, datetime.now(UTC) + timedelta(days=1), confirmed=True
    )
    with Session(repo.engine) as session, session.begin():
        session.get(ReferenceRow, str(key)).expires_at = datetime.now(UTC) - timedelta(seconds=1)
    with pytest.raises(PermissionError):
        service.read(key)
    from pathlib import Path

    original = Path.unlink

    def unavailable(path, *args, **kwargs):
        if path == service.path(key):
            raise OSError("synthetic filesystem unavailable")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unavailable)
    with pytest.raises(OSError):
        service.cleanup()
    assert repo.get(entity.id).reference_ids == []
    with pytest.raises(PermissionError):
        service.read(key)
    monkeypatch.setattr(Path, "unlink", original)
    assert service.cleanup() == 1
    repo.close()


@pytest.mark.skipif(not os.environ.get("MNEMOS_TEST_POSTGRES"), reason="real PostgreSQL opt-in")
def test_postgres_reference_audit_encrypted_file_retire(tmp_path):
    from sqlalchemy.schema import CreateSchema, DropSchema

    repo = EntityRepository(os.environ["MNEMOS_TEST_POSTGRES"])
    original = repo.engine
    schema = "test_references_" + uuid4().hex
    with original.begin() as connection:
        connection.execute(CreateSchema(schema))
    repo.engine = original.execution_options(schema_translate_map={None: schema})
    try:
        Base.metadata.create_all(repo.engine)
        service, entity, _, _, jpeg, provenance = fixture(repo, tmp_path)
        key = service.store(
            entity.id, jpeg, provenance, datetime.now(UTC) + timedelta(days=1), confirmed=True
        )
        assert service.read(key) == jpeg
        service.retire(key, entity.name, confirmed=True)
        assert service.cleanup() == 1
    finally:
        with original.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        repo.close()


def test_api_server_crop_no_upload_auth_expiry_and_delete(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from mnemos import api

    repo = EntityRepository("sqlite:///" + str(tmp_path / "http.db"))
    _, entity, capture, track, jpeg, _ = fixture(repo, tmp_path)
    capture.start = lambda: None
    capture.track_bindings.clear()
    monkeypatch.setattr(api, "build_capture", lambda *args, **kwargs: capture)
    layout = RuntimeLayout(tmp_path)
    layout.configure = lambda: None
    token = "synthetic-reference-api-owner-token-123456789"
    headers = {"Authorization": "Bearer " + token}
    entity.id = uuid4()
    entity.owner_id = None
    with TestClient(api.create_app(repo, token, layout)) as client:
        assert (
            client.post(
                "/entities", json=entity.model_dump(mode="json"), headers=headers
            ).status_code
            == 201
        )
        client.post("/capture/start", json={"microphone": False}, headers=headers)
        path = f"/capture/{capture.id}/tracks/{track}"
        assert client.post(
            path + "/bind",
            json={"entity_id": str(entity.id), "confirm_observed_object": True},
            headers=headers,
        ).json()["bound"]
        payload = {
            "entity_id": str(entity.id),
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            "confirm_object_only_reference": True,
        }
        assert client.post(path + "/reference", json=payload).status_code == 401
        assert (
            client.post(
                path + "/reference",
                json={**payload, "confirm_object_only_reference": False},
                headers=headers,
            ).status_code
            == 403
        )
        assert (
            client.post(
                path + "/reference", json={**payload, "jpeg": "untrusted"}, headers=headers
            ).status_code
            == 422
        )
        result = client.post(path + "/reference", json=payload, headers=headers)
        assert result.status_code == 201
        key = result.json()["id"]
        listing = client.get(f"/objects/{entity.id}/references", headers=headers)
        assert listing.status_code == 200 and listing.headers["cache-control"] == "no-store"
        assert [row["id"] for row in listing.json()] == [key]
        assert set(listing.json()[0]) == {"id", "expires_at", "observed_at", "quality"}
        assert listing.json()[0]["quality"]["warnings"] == ["low-contrast", "low-edge-detail"]
        assert client.get(f"/objects/{entity.id}/references").status_code == 401
        assert client.get(f"/references/{key}/image").status_code == 401
        response = client.get(f"/references/{key}/image", headers=headers)
        assert response.content == jpeg and response.headers["cache-control"] == "no-store"
        assert (
            client.post(
                f"/references/{key}/delete", json={"confirmed_name": entity.name}, headers=headers
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/references/{key}/delete",
                json={"confirmed_name": entity.name, "confirm_irreversible": True},
                headers=headers,
            ).status_code
            == 200
        )
        assert client.get(f"/references/{key}/image", headers=headers).status_code in (403, 404)
        assert client.get(f"/entities/{entity.id}", headers=headers).json()["reference_ids"] == []
        assert client.get(f"/objects/{entity.id}/references", headers=headers).json() == []


def test_reference_file_permissions_and_missing_key_fail_closed(tmp_path):
    repo = EntityRepository("sqlite:///" + str(tmp_path / "private.db"))
    service, entity, _, _, jpeg, provenance = fixture(repo, tmp_path)
    key = service.store(
        entity.id, jpeg, provenance, datetime.now(UTC) + timedelta(days=1), confirmed=True
    )
    service.path(key).chmod(0o644)
    with pytest.raises(PermissionError):
        service.read(key)
    service.path(key).chmod(0o600)
    original = service.key.path.read_bytes()
    service.key.path.unlink()
    with pytest.raises(PermissionError):
        service.read(key)
    with pytest.raises(FileNotFoundError):
        service.store(
            entity.id, jpeg, provenance, datetime.now(UTC) + timedelta(days=1), confirmed=True
        )
    assert not service.key.path.exists() and repo.get(entity.id).reference_ids == [key]
    service.key.path.write_bytes(original)
    service.key.path.chmod(0o600)
    assert service.read(key) == jpeg
    repo.close()


def test_idle_reference_frame_expires_without_new_source_data(tmp_path, monkeypatch):
    import asyncio
    import threading

    repo = EntityRepository("sqlite:///" + str(tmp_path / "idle.db"))
    _, _, capture, _, _, _ = fixture(repo, tmp_path)
    capture.last_observed = time.monotonic() - 3
    done = threading.Event()

    async def finish(_seconds):
        done.set()

    monkeypatch.setattr(asyncio, "sleep", finish)
    asyncio.run(capture.expire_buffers(done))
    assert capture.reference_frame is None
    repo.close()
