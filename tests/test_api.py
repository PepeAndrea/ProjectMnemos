from uuid import uuid4

from fastapi.testclient import TestClient
from mnemos.api import create_app
from mnemos.domain import Entity, Provenance, Retention
from mnemos.storage import EntityRepository

TOKEN = "test-only-owner-token-32-characters"


def test_registry_authorization_privacy_and_reload(tmp_path):
    url = "sqlite:///" + str(tmp_path / "registry.db")
    repo = EntityRepository(url)
    repo.initialize()
    entity = Entity(
        kind="object",
        name="il mio zaino",
        confidence=1,
        provenance=Provenance(source_id="owner", method="human"),
        retention=Retention(scope="persistent", purpose="enrollment"),
        enrolled=True,
    )
    headers = {"Authorization": "Bearer " + TOKEN}
    with TestClient(create_app(repo, TOKEN)) as client:
        assert client.get("/health").json()["assistant"] == "Tobi"
        assert client.get("/entities").status_code == 401
        assert (
            client.post(
                "/entities", json=entity.model_dump(mode="json"), headers=headers
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/entities", json=entity.model_dump(mode="json"), headers=headers
            ).status_code
            == 409
        )
        assert client.get("/entities?limit=1001", headers=headers).status_code == 422
        assert client.get("/entities/" + str(uuid4()), headers=headers).status_code == 404
        entity.name = "zaino lavoro"
        assert (
            client.put(
                "/entities/" + str(entity.id), json=entity.model_dump(mode="json"), headers=headers
            ).status_code
            == 200
        )
        person = {**entity.model_dump(mode="json"), "kind": "person"}
        assert client.post("/entities", json=person, headers=headers).status_code == 422
    fresh = EntityRepository(url)
    assert fresh.get(entity.id).name == "zaino lavoro"
    fresh.close()


def test_missing_auth_configuration_fails_closed(tmp_path):
    repo = EntityRepository("sqlite:///" + str(tmp_path / "none.db"))
    with TestClient(create_app(repo, "short")) as client:
        assert client.get("/entities").status_code == 503


def test_capture_auth_and_native_consent_fail_closed(tmp_path):
    repo = EntityRepository("sqlite:///" + str(tmp_path / "capture.db"))
    headers = {"Authorization": "Bearer " + TOKEN}
    with TestClient(create_app(repo, TOKEN)) as client:
        assert client.get("/capture/status").status_code == 401
        assert client.post("/capture/start", json={"mode": "replay"}).status_code == 401
        assert (
            client.post("/capture/start", json={"mode": "native"}, headers=headers).status_code
            == 403
        )
        assert (
            client.post(
                "/capture/start",
                json={
                    "mode": "native",
                    "camera": False,
                    "microphone": True,
                    "camera_consent": True,
                },
                headers=headers,
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/capture/start", json={"mode": "native", "camera_consent": "true"}, headers=headers
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/capture/start",
                json={
                    "mode": "native",
                    "camera": False,
                    "microphone": False,
                    "camera_index": 2,
                },
                headers=headers,
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/capture/start",
                json={"mode": "native", "camera_index": 5},
                headers=headers,
            ).status_code
            == 422
        )
        assert client.get("/capture/frame", headers=headers).status_code == 404
        assert client.get("/capture/status", headers=headers).headers["Cache-Control"] == "no-store"
        assert (
            client.post(
                "/capture/start",
                json={"mode": "speech-replay", "camera": False, "transcribe": "true"},
                headers=headers,
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/capture/start",
                json={
                    "mode": "speech-replay",
                    "camera": False,
                    "microphone": False,
                    "transcribe": True,
                },
                headers=headers,
            ).status_code
            == 422
        )
        assert client.post("/capture/stop", headers=headers).json()["state"] == "idle"


def test_one_capture_session_and_stop_clear_preview(tmp_path, monkeypatch):
    from mnemos.capture import CaptureSession
    from test_capture import FakeDetector, FakeSource

    factory_options = []

    def build(*args, **kwargs):
        factory_options.append(kwargs)
        capture = CaptureSession(FakeSource(), FakeSource(), FakeDetector(), FakeDetector())
        capture.start = lambda: setattr(capture, "state", "running")
        return capture

    monkeypatch.setattr("mnemos.api.build_capture", build)
    repo = EntityRepository("sqlite:///" + str(tmp_path / "capture.db"))
    headers = {"Authorization": "Bearer " + TOKEN}
    with TestClient(create_app(repo, TOKEN)) as client:
        response = client.post("/capture/start", json={"mode": "replay"}, headers=headers)
        assert response.status_code == 200
        assert response.json()["recording"] is False
        assert client.post("/capture/stop", headers=headers).json()["state"] == "stopped"
        assert client.get("/capture/frame", headers=headers).status_code == 404
        assert client.get("/capture/status", headers=headers).json()["audio_buffer_bytes"] == 0
        selected = client.post(
            "/capture/start",
            json={
                "mode": "native",
                "camera": True,
                "microphone": False,
                "camera_consent": True,
                "camera_index": 3,
            },
            headers=headers,
        )
        assert selected.status_code == 200
        assert factory_options[-1]["camera_index"] == 3
        assert client.post("/capture/stop", headers=headers).json()["state"] == "stopped"


def test_temporal_reminder_auth_validation_and_api_reload(tmp_path):
    from datetime import UTC, datetime, timedelta

    from mnemos.domain import Reminder, Trigger
    from mnemos.scheduler import TemporalScheduler

    url = "sqlite:///" + str(tmp_path / "reminder-api.db")
    repo = EntityRepository(url)
    repo.initialize()
    headers = {"Authorization": "Bearer " + TOKEN}
    reminder = Reminder(
        text="Synthetic HTTP reminder",
        trigger=Trigger(due_at=datetime.now(UTC) + timedelta(hours=1)),
        provenance=Provenance(source_id="test-owner", method="synthetic"),
    )
    with TestClient(create_app(repo, TOKEN)) as client:
        assert client.post("/reminders", json=reminder.model_dump(mode="json")).status_code == 401
        assert client.get("/notifications").status_code == 401
        assert (
            client.post(
                "/reminders", json=reminder.model_dump(mode="json"), headers=headers
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/reminders", json=reminder.model_dump(mode="json"), headers=headers
            ).status_code
            == 409
        )
        assert client.get("/notifications", headers=headers).json() == []
        assert client.get("/notifications?limit=1001", headers=headers).status_code == 422
    fresh = EntityRepository(url)
    TemporalScheduler(fresh.engine, uuid4()).tick(datetime.now(UTC) + timedelta(hours=2))
    with TestClient(create_app(fresh, TOKEN)) as client:
        assert client.get("/reminders", headers=headers).json()[0]["state"] == "notified"
        assert client.get("/notifications", headers=headers).json()[0]["reminder_id"] == str(
            reminder.id
        )


def test_http_person_consent_and_protected_reference_bypass_rejected(tmp_path):
    repo = EntityRepository("sqlite:///" + str(tmp_path / "governed-api.db"))
    repo.initialize()
    headers = {"Authorization": "Bearer " + TOKEN}
    body = Entity(
        kind="person",
        name="synthetic claimed person",
        enrolled=True,
        biometric_consent=True,
        confidence=1,
        provenance=Provenance(source_id="test", method="synthetic"),
        retention=Retention(scope="persistent", purpose="synthetic"),
    ).model_dump(mode="json")
    with TestClient(create_app(repo, TOKEN)) as client:
        assert client.post("/entities", json=body, headers=headers).status_code == 403
        body.update(kind="object", biometric_consent=False, reference_ids=[str(uuid4())])
        assert client.post("/entities", json=body, headers=headers).status_code == 403
        assert client.get("/entities", headers=headers).json() == []


def test_http_delete_requires_strict_confirmation_and_current_name(tmp_path):
    repo = EntityRepository("sqlite:///" + str(tmp_path / "delete-api.db"))
    repo.initialize()
    headers = {"Authorization": "Bearer " + TOKEN}
    body = Entity(
        kind="object",
        name="Synthetic deletion fixture",
        confidence=1,
        enrolled=True,
        provenance=Provenance(source_id="test", method="synthetic"),
        retention=Retention(scope="persistent", purpose="synthetic"),
    ).model_dump(mode="json")
    path = "/entities/" + body["id"] + "/delete"
    with TestClient(create_app(repo, TOKEN)) as client:
        assert client.post(path, json={"confirmed_name": body["name"]}).status_code == 401
        assert client.post("/entities", json=body, headers=headers).status_code == 201
        assert (
            client.post(path, json={"confirmed_name": body["name"]}, headers=headers).status_code
            == 403
        )
        assert (
            client.post(
                path,
                json={"confirmed_name": body["name"], "confirm_irreversible": "true"},
                headers=headers,
            ).status_code
            == 422
        )
        assert (
            client.post(
                path,
                json={"confirmed_name": "wrong", "confirm_irreversible": True},
                headers=headers,
            ).status_code
            == 403
        )
        deleted = client.post(
            path,
            json={"confirmed_name": body["name"], "confirm_irreversible": True},
            headers=headers,
        )
        assert deleted.status_code == 200 and deleted.json()["policy"]["allowed"]
        assert client.get("/entities/" + body["id"], headers=headers).status_code == 404


def test_server_owned_voice_review_auth_correction_retry_and_stop(tmp_path, monkeypatch):
    import time

    from mnemos.capture import CaptureSession
    from mnemos.speech_stream import TranscriptUpdate
    from mnemos.storage import LocalActionRow
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from test_capture import FakeSource

    sessions = []

    def build(*args, **kwargs):
        capture = CaptureSession(None, FakeSource())
        # Deliberate injected server-owned provider fixture; no client text endpoint.
        capture.start = lambda: setattr(capture, "state", "running")
        sessions.append(capture)
        return capture

    monkeypatch.setattr("mnemos.api.build_capture", build)
    repo = EntityRepository("sqlite:///" + str(tmp_path / "voice-api.db"))
    repo.initialize()
    headers = {"Authorization": "Bearer " + TOKEN}
    with TestClient(create_app(repo, TOKEN)) as client:
        status = client.post("/capture/start", json={"mode": "replay"}, headers=headers).json()
        capture = sessions[-1]
        capture.publish_speech(
            [
                TranscriptUpdate(
                    "final",
                    "synthetic",
                    time.monotonic() - 1,
                    time.monotonic(),
                    "Toby, remember this is my backpack.",
                    "en",
                    0.7,
                    False,
                    "anonymous-synthetic",
                )
            ]
        )
        proposal = client.get("/capture/status", headers=headers).json()["enrollment_proposals"][0]
        path = "/capture/" + status["id"] + "/enrollment/" + proposal["id"] + "/approve"
        assert client.get("/entities", headers=headers).json() == []
        body = {"name": "owner corrected backpack", "confirm_catalog_enrollment": True}
        assert client.post(path, json=body).status_code == 401
        assert client.post(path, json={"name": "bag"}, headers=headers).status_code == 403
        assert (
            client.post(
                path, json={**body, "confirm_catalog_enrollment": "true"}, headers=headers
            ).status_code
            == 422
        )
        assert (
            client.post(path, json={**body, "speaker_confidence": 1}, headers=headers).status_code
            == 422
        )
        from mnemos.registry import GovernedRegistry
        from sqlalchemy.exc import SQLAlchemyError

        original_save = GovernedRegistry.save

        def fail_database(*args, **kwargs):
            raise SQLAlchemyError("synthetic DB failure")

        monkeypatch.setattr(GovernedRegistry, "save", fail_database)
        assert client.post(path, json=body, headers=headers).status_code == 503
        assert capture.snapshot()["enrollment_proposals"][0]["state"] == "pending"
        assert client.get("/entities", headers=headers).json() == []
        monkeypatch.setattr(GovernedRegistry, "save", original_save)
        accepted = client.post(path, json=body, headers=headers)
        assert accepted.status_code == 201
        assert accepted.json()["name"] == body["name"]
        assert accepted.json()["provenance"]["source_id"] == "owner-voice-review"
        assert client.post(path, json=body, headers=headers).status_code == 404
        with Session(repo.engine) as session:
            audit = list(session.scalars(select(LocalActionRow)))
            assert len(audit) == 1
            assert audit[0].payload["result"]["reviewed_proposal_id"] == proposal["id"]
            assert "my backpack" not in str(audit[0].payload)
        capture.publish_speech(
            [
                TranscriptUpdate(
                    "second",
                    "synthetic",
                    time.monotonic() - 1,
                    time.monotonic(),
                    "Save this as another bag",
                    "en",
                    1,
                    False,
                    "anonymous",
                )
            ]
        )
        rejected = capture.snapshot()["enrollment_proposals"][0]
        reject_path = "/capture/" + status["id"] + "/enrollment/" + rejected["id"] + "/reject"
        assert client.post(reject_path, headers=headers).status_code == 200
        assert capture.snapshot()["enrollment_proposals"] == []
        client.post("/capture/stop", headers=headers)
        assert client.post(path, json=body, headers=headers).status_code == 409
        assert len(client.get("/entities", headers=headers).json()) == 1


def test_voice_approval_does_not_delay_stop_or_resurrect_volatile_state(tmp_path, monkeypatch):
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    from mnemos.capture import CaptureSession
    from mnemos.registry import GovernedRegistry
    from mnemos.speech_stream import TranscriptUpdate
    from test_capture import FakeSource

    capture = CaptureSession(None, FakeSource())
    capture.start = lambda: setattr(capture, "state", "running")
    monkeypatch.setattr("mnemos.api.build_capture", lambda *args, **kwargs: capture)
    started, release = threading.Event(), threading.Event()
    original_save = GovernedRegistry.save

    def delayed_save(*args, **kwargs):
        started.set()
        assert release.wait(3)
        return original_save(*args, **kwargs)

    monkeypatch.setattr(GovernedRegistry, "save", delayed_save)
    repo = EntityRepository("sqlite:///" + str(tmp_path / "stop-review.db"))
    repo.initialize()
    headers = {"Authorization": "Bearer " + TOKEN}
    with TestClient(create_app(repo, TOKEN)) as client, ThreadPoolExecutor(max_workers=1) as pool:
        client.post("/capture/start", json={"mode": "replay"}, headers=headers)
        capture.publish_speech(
            [
                TranscriptUpdate(
                    "final",
                    "synthetic",
                    time.monotonic() - 1,
                    time.monotonic(),
                    "Save this as a bag",
                    "en",
                    1,
                    False,
                    "anonymous",
                )
            ]
        )
        proposal = capture.snapshot()["enrollment_proposals"][0]
        path = "/capture/" + capture.id + "/enrollment/" + proposal["id"] + "/approve"
        body = {"name": "explicitly confirmed fixture", "confirm_catalog_enrollment": True}
        future = pool.submit(client.post, path, json=body, headers=headers)
        try:
            assert started.wait(1)
            assert client.post(path, json=body, headers=headers).status_code == 409
            at = time.monotonic()
            assert client.post("/capture/stop", headers=headers).json()["state"] == "stopped"
            assert time.monotonic() - at < 0.5
            assert capture.snapshot()["enrollment_proposals"] == []
        finally:
            release.set()
        assert future.result(timeout=3).status_code == 201
        assert capture.snapshot()["enrollment_proposals"] == []
        assert capture.snapshot()["transcripts"] == []
        assert len(client.get("/entities", headers=headers).json()) == 1


def test_person_consent_separate_scopes_auth_retention_and_revocation(tmp_path):
    from datetime import UTC, datetime, timedelta

    repo = EntityRepository("sqlite:///" + str(tmp_path / "person-api.db"))
    repo.initialize()
    headers = {"Authorization": "Bearer " + TOKEN}
    body = {
        "name": "Synthetic authorized subject",
        "face": True,
        "voice": False,
        "subject_permission_attested": True,
        "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
    }
    with TestClient(create_app(repo, TOKEN)) as client:
        assert client.post("/people", json=body).status_code == 401
        assert (
            client.post(
                "/people", json={**body, "subject_permission_attested": False}, headers=headers
            ).status_code
            == 403
        )
        assert (
            client.post("/people", json={**body, "face": False}, headers=headers).status_code == 403
        )
        assert (
            client.post("/people", json={**body, "face": "true"}, headers=headers).status_code
            == 422
        )
        assert (
            client.post(
                "/people",
                json={**body, "expires_at": datetime.now(UTC).replace(tzinfo=None).isoformat()},
                headers=headers,
            ).status_code
            == 422
        )
        created = client.post("/people", json=body, headers=headers)
        assert created.status_code == 201
        entity = created.json()
        path = "/people/" + entity["id"]
        listed = client.get("/people", headers=headers)
        assert listed.status_code == 200 and listed.headers["Cache-Control"] == "no-store"
        assert listed.json()[0]["face"] is True and listed.json()[0]["voice"] is False
        consent = client.get(path + "/consent", headers=headers)
        assert consent.status_code == 200 and consent.headers["Cache-Control"] == "no-store"
        assert consent.json()["face"] and not consent.json()["voice"]
        assert consent.json()["assurance"] == "owner-attested-subject-permission"
        renamed = client.put(
            path + "/name", json={"name": "Synthetic corrected subject"}, headers=headers
        )
        assert renamed.status_code == 200
        assert (
            client.put("/entities/" + entity["id"], json=entity, headers=headers).status_code == 403
        )
        assert (
            client.post(
                path + "/revoke",
                json={"confirmed_name": body["name"], "confirm_irreversible": True},
                headers=headers,
            ).status_code
            == 403
        )
        assert (
            client.post(
                path + "/revoke",
                json={"confirmed_name": renamed.json()["name"], "confirm_irreversible": True},
                headers=headers,
            ).status_code
            == 200
        )
        assert client.get("/entities/" + entity["id"], headers=headers).status_code == 404
        assert client.get(path + "/consent", headers=headers).json()["status"] == "revoked"
