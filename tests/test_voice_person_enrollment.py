import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from mnemos.api import create_app
from mnemos.biometrics import ConsentRow, PersonEnrollment
from mnemos.capture import CaptureSession
from mnemos.speech_stream import TranscriptUpdate
from mnemos.storage import EntityRepository, LocalActionRow
from sqlalchemy import event, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from test_capture import FakeSource

TOKEN = "synthetic-voice-person-owner-token-123456789"


def test_person_voice_review_requires_consent_and_atomic_audit(tmp_path):
    repo = EntityRepository("sqlite:///" + str(tmp_path / "voice-person.db"))
    repo.initialize()
    capture = CaptureSession(None, FakeSource())
    capture.start = lambda: setattr(capture, "state", "running")
    headers = {"Authorization": "Bearer " + TOKEN}
    with TestClient(
        create_app(repo, TOKEN, capture_factory=lambda *args, **kwargs: capture)
    ) as client:
        client.post("/capture/start", json={"mode": "replay"}, headers=headers)
        capture.publish_speech(
            [
                TranscriptUpdate(
                    "synthetic-final",
                    "synthetic",
                    time.monotonic() - 1,
                    time.monotonic(),
                    "Tobi, memorizza questa come nome sintetico.",
                    "it",
                    0.7,
                    False,
                    "anonymous-synthetic",
                )
            ]
        )
        proposal = capture.snapshot()["enrollment_proposals"][0]
        assert proposal["policy"]["allowed"] is False and repo.list() == []
        expected_id = next(iter(capture.enrollment.pending.values())).entity_id
        path = f"/capture/{capture.id}/enrollment/{proposal['id']}/approve-person"
        body = {
            "name": "Synthetic corrected person",
            "face": True,
            "voice": False,
            "subject_permission_attested": True,
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "confirm_person_enrollment": True,
        }
        assert client.post(path, json=body).status_code == 401
        for invalid in (
            {"confirm_person_enrollment": False},
            {"subject_permission_attested": False},
            {"face": False, "voice": False},
        ):
            assert client.post(path, json={**body, **invalid}, headers=headers).status_code == 403
        for invalid in (
            {"face": "true"},
            {"confirm_person_enrollment": "true"},
            {"speaker_confidence": 1},
            {"expires_at": "2026-10-10T10:00:00"},
        ):
            assert client.post(path, json={**body, **invalid}, headers=headers).status_code == 422
        assert repo.list() == []

        def fail(*args):
            raise SQLAlchemyError("synthetic audit failure")

        event.listen(LocalActionRow, "before_insert", fail)
        try:
            assert client.post(path, json=body, headers=headers).status_code == 503
        finally:
            event.remove(LocalActionRow, "before_insert", fail)
        assert (
            repo.list() == []
            and capture.snapshot()["enrollment_proposals"][0]["state"] == "pending"
        )
        with Session(repo.engine) as session:
            assert list(session.scalars(select(ConsentRow))) == []
        response = client.post(path, json=body, headers=headers)
        assert response.status_code == 201
        person = response.json()
        assert person["id"] == str(expected_id)
        assert person["kind"] == "person" and person["name"] == body["name"]
        assert person["provenance"]["source_id"] == "owner-reviewed-person-consent"
        consent = client.get(f"/people/{person['id']}/consent", headers=headers).json()
        assert consent["face"] is True and consent["voice"] is False
        assert consent["assurance"] == "owner-attested-subject-permission"
        assert capture.snapshot()["enrollment_proposals"] == []
        assert client.post(path, json=body, headers=headers).status_code == 404
        with Session(repo.engine) as session:
            audits = list(session.scalars(select(LocalActionRow)))
            assert len(audits) == 1
            params = audits[0].payload["result"]["proposal"]["params"]
            assert params["reviewed_proposal_id"] == proposal["id"]
            assert "nome sintetico" not in str(audits[0].payload)
            assert body["name"] not in str(audits[0].payload)
        client.post("/capture/stop", headers=headers)
        assert client.post(path, json=body, headers=headers).status_code == 409
        assert (
            client.post(
                f"/people/{person['id']}/revoke",
                json={"confirmed_name": body["name"], "confirm_irreversible": True},
                headers=headers,
            ).status_code
            == 200
        )


def test_stable_person_id_cannot_duplicate_or_convert_existing_object(tmp_path):
    from uuid import uuid4

    from mnemos.biometrics import BiometricKey
    from mnemos.domain import Entity, Provenance, Retention
    from mnemos.registry import GovernedRegistry

    repo = EntityRepository("sqlite:///" + str(tmp_path / "stable.db"))
    repo.initialize()
    owner = uuid4()
    registry = GovernedRegistry(repo, owner)
    entity = registry.save(
        Entity(
            kind="object",
            name="Synthetic object",
            enrolled=True,
            confidence=1,
            provenance=Provenance(source_id="synthetic", method="human"),
            retention=Retention(scope="persistent", purpose="explicit enrollment"),
        )
    )
    service = PersonEnrollment(repo, owner, BiometricKey(tmp_path / "private" / "key"))
    kwargs = {
        "face": True,
        "voice": False,
        "subject_permission_attested": True,
        "expires_at": datetime.now(UTC) + timedelta(days=1),
    }
    with pytest.raises(ValueError):
        service.grant("Synthetic person", entity_id=entity.id, **kwargs)
    assert repo.get(entity.id).kind == "object"
    key = uuid4()
    service.grant("Synthetic person", entity_id=key, reviewed_proposal_id=uuid4(), **kwargs)
    with pytest.raises(ValueError):
        service.grant("Synthetic person duplicate", entity_id=key, **kwargs)
    assert len(repo.list()) == 2 and not service.key.path.exists()
    assert service.status(UUID(str(key)))["status"] == "active"
    repo.close()


def test_person_review_commit_does_not_block_stop_or_restore_private_state(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    repo = EntityRepository("sqlite:///" + str(tmp_path / "stop-person.db"))
    repo.initialize()
    capture = CaptureSession(None, FakeSource())
    capture.start = lambda: setattr(capture, "state", "running")
    entered, release = Event(), Event()
    original = PersonEnrollment.grant

    def blocked_grant(self, *args, **kwargs):
        entered.set()
        assert release.wait(5), "synthetic blocked transaction was not released"
        return original(self, *args, **kwargs)

    monkeypatch.setattr(PersonEnrollment, "grant", blocked_grant)
    headers = {"Authorization": "Bearer " + TOKEN}
    with TestClient(
        create_app(repo, TOKEN, capture_factory=lambda *args, **kwargs: capture)
    ) as client:
        client.post("/capture/start", json={"mode": "replay"}, headers=headers)
        at = time.monotonic()
        capture.publish_speech(
            [
                TranscriptUpdate(
                    "synthetic-stop",
                    "synthetic",
                    at - 1,
                    at,
                    "Tobi, memorizza questa come persona sintetica.",
                    "it",
                    0.7,
                    False,
                    "anonymous-synthetic",
                )
            ]
        )
        proposal = capture.snapshot()["enrollment_proposals"][0]
        path = f"/capture/{capture.id}/enrollment/{proposal['id']}/approve-person"
        body = {
            "name": "Synthetic stopped review",
            "face": False,
            "voice": True,
            "subject_permission_attested": True,
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "confirm_person_enrollment": True,
        }
        with ThreadPoolExecutor(max_workers=2) as pool:
            approving = pool.submit(client.post, path, json=body, headers=headers)
            try:
                assert entered.wait(2)
                assert client.post(path, json=body, headers=headers).status_code == 409
                stopping = pool.submit(client.post, "/capture/stop", headers=headers)
                stopped = stopping.result(timeout=2)
                assert stopped.status_code == 200 and stopped.json()["state"] == "stopped"
                assert capture.snapshot()["transcripts"] == []
                assert capture.snapshot()["enrollment_proposals"] == []
                assert repo.list() == []
            finally:
                release.set()
            assert approving.result(timeout=2).status_code == 201
        assert capture.snapshot()["transcripts"] == []
        assert capture.snapshot()["enrollment_proposals"] == []
        assert len(repo.list()) == 1
        assert client.post(path, json=body, headers=headers).status_code == 409
        person = repo.list()[0]
        assert (
            client.post(
                f"/people/{person.id}/revoke",
                headers=headers,
                json={"confirmed_name": person.name, "confirm_irreversible": True},
            ).status_code
            == 200
        )
    repo.close()
