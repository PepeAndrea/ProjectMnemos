import os
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from mnemos.biometrics import BiometricKey, ConsentRow, PersonEnrollment
from mnemos.capture import CaptureSession
from mnemos.face_references import FaceReferences
from mnemos.media import VideoFrame
from mnemos.references import ObjectReferences
from mnemos.runtime import RuntimeLayout
from mnemos.storage import Base, EntityRepository, FaceReferenceRow, LocalActionRow
from mnemos.tracking import TrackUpdate
from mnemos.vision import Box, Detection
from sqlalchemy import event, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


def fixture(repo, root, owner=None, *, face=True):
    repo.initialize()
    owner = owner or uuid4()
    persons = PersonEnrollment(repo, owner, BiometricKey(root / "private" / "vector-key"))
    person = persons.grant(
        "Synthetic face reference subject",
        face=face,
        voice=True,
        subject_permission_attested=True,
        expires_at=datetime.now(UTC) + timedelta(hours=2),
    )
    service = FaceReferences(repo, owner, RuntimeLayout(root))
    capture = CaptureSession(object(), None)
    capture.state = "running"
    track = uuid4()
    detection = Detection("face", 0.9, Box(16, 16, 96, 96), "synthetic-face", 1)
    capture.publish_tracks([TrackUpdate("enter", str(track), detection)], time.monotonic())
    capture.reference_frame = VideoFrame(
        "synthetic-face",
        1,
        time.monotonic(),
        datetime.now(UTC),
        128,
        128,
        "bgr24",
        bytes([40, 100, 70]) * (128 * 128),
    )
    capture.detections = [{"label": "face", "box": {"x": 16, "y": 16, "width": 96, "height": 96}}]
    jpeg, provenance = capture.face_crop(track)
    return persons, person, service, capture, track, jpeg, provenance


def save(service, person, jpeg, provenance):
    return service.store(
        person.id,
        jpeg,
        provenance,
        datetime.now(UTC) + timedelta(hours=1),
        confirmed=True,
        confirmed_name=person.name,
    )


def test_face_reference_consent_name_separation_and_revocation(tmp_path):
    repo = EntityRepository("sqlite:///" + str(tmp_path / "face.db"))
    persons, person, service, capture, track, jpeg, provenance = fixture(repo, tmp_path)
    for invalid in ({"confirmed": False}, {"confirmed_name": "wrong name"}):
        with pytest.raises(PermissionError):
            service.store(
                person.id,
                jpeg,
                provenance,
                datetime.now(UTC) + timedelta(hours=1),
                **{"confirmed": True, "confirmed_name": person.name, **invalid},
            )
    with pytest.raises(PermissionError):
        service.store(
            person.id,
            jpeg,
            provenance,
            datetime.now(UTC) + timedelta(hours=3),
            confirmed=True,
            confirmed_name=person.name,
        )
    assert not service.key.path.exists()
    key = save(service, person, jpeg, provenance)
    assert service.read(key) == jpeg and service.path(key).read_bytes() != jpeg
    assert service.path(key).stat().st_mode & 0o777 == 0o600
    assert not persons.key.path.exists() and repo.get(person.id).reference_ids == []
    objects = ObjectReferences(repo, service.owner, RuntimeLayout(tmp_path))
    with pytest.raises(KeyError):
        objects.read(key)
    with pytest.raises(PermissionError):
        objects.store(
            person.id, jpeg, provenance, datetime.now(UTC) + timedelta(hours=1), confirmed=True
        )
    with Session(repo.engine) as session:
        row = session.get(FaceReferenceRow, str(key))
        assert row.payload["asset_kind"] == "consented-face-reference"
        assert row.payload["consent_id"] == persons.status(person.id)["id"]
    capture.clear_media()
    with pytest.raises(KeyError):
        capture.face_crop(track)
    assert service.read(key) == jpeg
    persons.revoke(person.id, person.name, confirmed=True)
    with pytest.raises((KeyError, PermissionError)):
        service.read(key)
    assert service.path(key).exists() and service.cleanup() == 1
    assert not service.path(key).exists()
    with Session(repo.engine) as session:
        assert all(
            person.name not in str(row.payload) for row in session.scalars(select(LocalActionRow))
        )
    repo.close()


def test_face_scope_and_expiry_fail_closed_without_waiting_for_cleanup(tmp_path):
    repo = EntityRepository("sqlite:///" + str(tmp_path / "scope.db"))
    persons, person, service, _capture, _track, jpeg, provenance = fixture(
        repo, tmp_path, face=False
    )
    with pytest.raises(PermissionError):
        save(service, person, jpeg, provenance)
    assert not service.key.path.exists()
    with Session(repo.engine) as session, session.begin():
        consent = session.scalar(select(ConsentRow).where(ConsentRow.entity_id == str(person.id)))
        consent.payload = {**consent.payload, "face": True}
    key = save(service, person, jpeg, provenance)
    with Session(repo.engine) as session, session.begin():
        session.scalar(select(ConsentRow)).expires_at = datetime.now(UTC) - timedelta(seconds=1)
    with pytest.raises(PermissionError):
        service.read(key)
    with pytest.raises(PermissionError):
        service.list(person.id)
    assert persons.purge_expired() == 1 and service.cleanup() == 1
    assert repo.list() == []
    repo.close()


def test_face_crop_rejects_stale_partial_wrong_source_and_other_face(tmp_path):
    repo = EntityRepository("sqlite:///" + str(tmp_path / "crop.db"))
    _persons, _person, _service, capture, track, _jpeg, _provenance = fixture(repo, tmp_path)
    original = capture.reference_frame
    capture.reference_frame = replace(original, source_id="other-source")
    with pytest.raises(ValueError):
        capture.face_crop(track)
    capture.reference_frame = original
    capture.detections.append(
        {"label": "face", "box": {"x": 25, "y": 25, "width": 80, "height": 80}}
    )
    with pytest.raises(PermissionError):
        capture.face_crop(track)
    capture.detections = []
    capture.visible_tracks[str(track)]["box"]["width"] = 20
    with pytest.raises(ValueError):
        capture.face_crop(track)
    capture.last_observed = time.monotonic() - 3
    with pytest.raises(KeyError):
        capture.face_crop(track)
    repo.close()


def test_face_audit_failure_key_loss_and_cleanup_retry(tmp_path, monkeypatch):
    from pathlib import Path

    repo = EntityRepository("sqlite:///" + str(tmp_path / "fail.db"))
    persons, person, service, _capture, _track, jpeg, provenance = fixture(repo, tmp_path)

    def fail(*args):
        raise SQLAlchemyError("synthetic audit failure")

    event.listen(LocalActionRow, "before_insert", fail)
    try:
        with pytest.raises(SQLAlchemyError):
            save(service, person, jpeg, provenance)
    finally:
        event.remove(LocalActionRow, "before_insert", fail)
    assert service.list(person.id) == [] and not list(service.folder.glob("*.enc"))
    key = save(service, person, jpeg, provenance)
    original_key = service.key.path.read_bytes()
    service.key.path.unlink()
    with pytest.raises(PermissionError):
        service.read(key)
    with pytest.raises(FileNotFoundError):
        save(service, person, jpeg, provenance)
    assert not service.key.path.exists()
    service.key.path.write_bytes(original_key)
    service.key.path.chmod(0o600)
    event.listen(LocalActionRow, "before_insert", fail)
    try:
        with pytest.raises(SQLAlchemyError):
            persons.revoke(person.id, person.name, confirmed=True)
    finally:
        event.remove(LocalActionRow, "before_insert", fail)
    assert service.read(key) == jpeg
    persons.revoke(person.id, person.name, confirmed=True)
    original_unlink = Path.unlink

    def blocked(path, *args, **kwargs):
        if path == service.path(key):
            raise OSError("synthetic storage failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", blocked)
    with pytest.raises(OSError):
        service.cleanup()
    with pytest.raises((KeyError, PermissionError)):
        service.read(key)
    monkeypatch.setattr(Path, "unlink", original_unlink)
    assert service.cleanup() == 1
    repo.close()


def test_face_http_requires_server_crop_and_valid_named_consent(tmp_path):
    from fastapi.testclient import TestClient
    from mnemos.api import create_app

    repo = EntityRepository("sqlite:///" + str(tmp_path / "http.db"))
    owner = uuid5(NAMESPACE_URL, "mnemos:single-installation:owner")
    _persons, person, _service, capture, track, jpeg, _provenance = fixture(repo, tmp_path, owner)
    capture.start = lambda: None
    token = "synthetic-face-reference-test-token-123456789"
    headers = {"Authorization": "Bearer " + token}
    with TestClient(
        create_app(
            repo, token, RuntimeLayout(tmp_path), capture_factory=lambda *args, **kwargs: capture
        )
    ) as client:
        client.post("/capture/start", json={"mode": "replay"}, headers=headers)
        path = f"/capture/{capture.id}/faces/{track}/reference"
        body = {
            "entity_id": str(person.id),
            "confirmed_name": person.name,
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "confirm_face_reference": True,
        }
        assert client.post(path, json=body).status_code == 401
        for invalid in ({"confirm_face_reference": False}, {"confirmed_name": "wrong"}):
            assert client.post(path, headers=headers, json={**body, **invalid}).status_code == 403
        for invalid in (
            {"confirm_face_reference": "true"},
            {"jpeg": "untrusted"},
            {"speaker_confidence": 1},
            {"box": {}},
        ):
            assert client.post(path, headers=headers, json={**body, **invalid}).status_code == 422
        result = client.post(path, headers=headers, json=body)
        assert result.status_code == 201
        key = result.json()["id"]
        assert client.get(f"/face-references/{key}/image").status_code == 401
        image = client.get(f"/face-references/{key}/image", headers=headers)
        assert image.content == jpeg and image.headers["cache-control"] == "no-store"
        assert client.get(f"/references/{key}/image", headers=headers).status_code == 404
        assert len(client.get(f"/people/{person.id}/face-references", headers=headers).json()) == 1
        client.post("/capture/stop", headers=headers)
        assert client.get(f"/face-references/{key}/image", headers=headers).status_code == 200
        assert client.post(path, headers=headers, json=body).status_code in (404, 409)
        client.post(
            f"/people/{person.id}/revoke",
            headers=headers,
            json={"confirmed_name": person.name, "confirm_irreversible": True},
        )
        assert client.get(f"/face-references/{key}/image", headers=headers).status_code in (
            403,
            404,
        )


@pytest.mark.skipif(not os.environ.get("MNEMOS_TEST_POSTGRES"), reason="real PostgreSQL opt-in")
def test_postgres_face_store_serializes_with_consent_revocation(tmp_path):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError
    from threading import Event

    from sqlalchemy.schema import CreateSchema, DropSchema

    repo = EntityRepository(os.environ["MNEMOS_TEST_POSTGRES"])
    original_engine = repo.engine
    schema = "test_face_reference_" + uuid4().hex
    with original_engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    repo.engine = original_engine.execution_options(schema_translate_map={None: schema})
    entered, release = Event(), Event()

    def block(*args):
        entered.set()
        assert release.wait(5)

    try:
        Base.metadata.create_all(repo.engine)
        persons, person, service, _capture, _track, jpeg, provenance = fixture(repo, tmp_path)
        event.listen(FaceReferenceRow, "before_insert", block)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                storing = pool.submit(save, service, person, jpeg, provenance)
                try:
                    assert entered.wait(2)
                    revoking = pool.submit(persons.revoke, person.id, person.name, confirmed=True)
                    with pytest.raises(TimeoutError):
                        revoking.result(timeout=0.1)
                finally:
                    release.set()
                key = storing.result(timeout=3)
                revoking.result(timeout=3)
        finally:
            event.remove(FaceReferenceRow, "before_insert", block)
        with pytest.raises((KeyError, PermissionError)):
            service.read(key)
        assert service.cleanup() == 1 and repo.list() == []
    finally:
        release.set()
        with original_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        repo.close()
