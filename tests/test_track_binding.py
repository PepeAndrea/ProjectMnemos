import os
import time
from uuid import UUID, uuid4

import pytest
from mnemos.capture import CaptureSession
from mnemos.domain import Entity, Provenance, Retention
from mnemos.registry import GovernedRegistry
from mnemos.storage import EntityRepository, LocalActionRow
from mnemos.track_binding import authorize_binding
from mnemos.tracking import TrackUpdate
from mnemos.vision import Box, Detection
from sqlalchemy import event, select
from sqlalchemy.orm import Session


def session_track(label="backpack"):
    capture = CaptureSession(object(), None)
    capture.state = "running"
    key = uuid4()
    detection = Detection(label, 0.9, Box(0, 0, 20, 20), "synthetic", 1)
    capture.publish_tracks([TrackUpdate("enter", str(key), detection)], time.monotonic())
    return capture, key, detection


def test_track_binding_is_explicit_volatile_and_never_reidentifies():
    capture, key, detection = session_track()
    claim = capture.claim_track(key)
    with pytest.raises(ValueError):
        claim = capture.claim_track(key)
    entity_id = uuid4()
    assert capture.finish_binding(key, entity_id, claim["claim_id"])
    assert capture.snapshot()["tracks"][0]["entity_id"] == str(entity_id)
    capture.publish_tracks([TrackUpdate("update", str(key), detection)], time.monotonic())
    assert capture.track_bindings[str(key)] == str(entity_id)
    capture.publish_tracks([], time.monotonic())
    assert capture.track_bindings == {}
    capture.publish_tracks([TrackUpdate("update", str(key), detection)], time.monotonic())
    assert capture.snapshot()["tracks"][0]["entity_id"] is None
    claim = capture.claim_track(key)
    capture.publish_tracks([], time.monotonic())
    capture.publish_tracks([TrackUpdate("update", str(key), detection)], time.monotonic())
    assert not capture.finish_binding(
        key, entity_id, claim["claim_id"]
    )  # lost while audit was in flight
    old_claim = claim
    claim = capture.claim_track(key)
    assert not capture.finish_binding(key, uuid4(), old_claim["claim_id"])
    assert capture.binding_claims[str(key)] == claim["claim_id"]
    capture.clear_media()
    assert not capture.finish_binding(key, entity_id, claim["claim_id"])
    assert capture.snapshot()["tracks"] == []


def test_person_unknown_and_stale_tracks_cannot_gain_named_binding():
    for label in ("person", "face"):
        capture, key, _ = session_track(label)
        with pytest.raises(PermissionError):
            capture.claim_track(key)
    capture, key, _ = session_track()
    with pytest.raises(KeyError):
        capture.claim_track(uuid4())
    capture.last_observed = time.monotonic() - 3
    with pytest.raises(KeyError):
        capture.claim_track(key)
    capture.state = "stopped"
    with pytest.raises(ValueError):
        capture.claim_track(key)


def test_policy_owner_and_audit_failure_leave_no_association(tmp_path):
    repo = EntityRepository("sqlite:///" + str(tmp_path / "binding.db"))
    repo.initialize()
    owner = uuid4()
    entity = GovernedRegistry(repo, owner).save(
        Entity(
            kind="object",
            name="Synthetic backpack",
            enrolled=True,
            confidence=1,
            provenance=Provenance(source_id="synthetic", method="human"),
            retention=Retention(scope="persistent", purpose="explicit enrollment"),
        )
    )
    capture, key, _ = session_track()
    with pytest.raises(PermissionError):
        authorize_binding(repo, owner, UUID(capture.id), key, entity.id, confirmed=False)
    with pytest.raises(PermissionError):
        authorize_binding(repo, uuid4(), UUID(capture.id), key, entity.id, confirmed=True)
    with pytest.raises(KeyError):
        authorize_binding(repo, owner, UUID(capture.id), key, uuid4(), confirmed=True)

    def fail(*args):
        raise RuntimeError("synthetic audit error")

    event.listen(LocalActionRow, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError):
            authorize_binding(repo, owner, UUID(capture.id), key, entity.id, confirmed=True)
    finally:
        event.remove(LocalActionRow, "before_insert", fail)
    authorize_binding(repo, owner, UUID(capture.id), key, entity.id, confirmed=True)
    with Session(repo.engine) as session:
        audits = list(session.scalars(select(LocalActionRow)))
        assert len(audits) == 2
        assert "Synthetic backpack" not in str([row.payload for row in audits])
        assert audits[-1].payload["policy"]["risk"] == "confirmation"
    assert repo.get(entity.id).reference_ids == []
    repo.close()


def test_binding_api_auth_confirmation_retry_and_stop(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from mnemos import api
    from sqlalchemy.exc import SQLAlchemyError

    capture, key, _ = session_track()
    capture.start = lambda: None
    monkeypatch.setattr(api, "build_capture", lambda *args, **kwargs: capture)
    repo = EntityRepository("sqlite:///" + str(tmp_path / "api-binding.db"))
    repo.initialize()
    token = "synthetic-owner-token-only-32-characters"
    headers = {"Authorization": "Bearer " + token}
    entity = Entity(
        kind="object",
        name="Synthetic selected object",
        enrolled=True,
        confidence=1,
        provenance=Provenance(source_id="synthetic", method="human"),
        retention=Retention(scope="persistent", purpose="explicit enrollment"),
    )
    with TestClient(api.create_app(repo, token)) as client:
        assert (
            client.post(
                "/entities", json=entity.model_dump(mode="json"), headers=headers
            ).status_code
            == 201
        )
        client.post("/capture/start", json={"microphone": False}, headers=headers)
        path = f"/capture/{capture.id}/tracks/{key}/bind"
        payload = {"entity_id": str(entity.id), "confirm_observed_object": True}
        assert client.post(path, json=payload).status_code == 401
        assert (
            client.post(path, json={"entity_id": str(entity.id)}, headers=headers).status_code
            == 403
        )
        assert (
            client.post(
                path, json={**payload, "confirm_observed_object": "true"}, headers=headers
            ).status_code
            == 422
        )
        real = api.authorize_binding

        def fail(*args, **kwargs):
            raise SQLAlchemyError("synthetic unavailable")

        monkeypatch.setattr(api, "authorize_binding", fail)
        assert client.post(path, json=payload, headers=headers).status_code == 503
        assert capture.binding_claims == capture.track_bindings == {}
        monkeypatch.setattr(api, "authorize_binding", real)
        result = client.post(path, json=payload, headers=headers)
        assert result.status_code == 200 and result.json()["bound"] is True
        assert client.post(path, json=payload, headers=headers).status_code == 409
        client.post("/capture/stop", headers=headers)
        assert client.get("/capture/status", headers=headers).json()["tracks"] == []
        assert client.post(path, json=payload, headers=headers).status_code == 409


@pytest.mark.skipif(not os.environ.get("MNEMOS_TEST_POSTGRES"), reason="real PostgreSQL opt-in")
def test_postgres_owner_binding_audit_in_isolated_schema():
    from mnemos.storage import Base
    from sqlalchemy.schema import CreateSchema, DropSchema

    repo = EntityRepository(os.environ["MNEMOS_TEST_POSTGRES"])
    original = repo.engine
    schema = "test_track_binding_" + uuid4().hex
    with original.begin() as connection:
        connection.execute(CreateSchema(schema))
    repo.engine = original.execution_options(schema_translate_map={None: schema})
    try:
        Base.metadata.create_all(repo.engine)
        owner = uuid4()
        entity = GovernedRegistry(repo, owner).save(
            Entity(
                kind="object",
                name="Synthetic PG selected object",
                enrolled=True,
                confidence=1,
                provenance=Provenance(source_id="synthetic", method="human"),
                retention=Retention(scope="persistent", purpose="explicit enrollment"),
            )
        )
        authorize_binding(repo, owner, uuid4(), uuid4(), entity.id, confirmed=True)
        with Session(repo.engine) as session:
            audits = list(session.scalars(select(LocalActionRow)))
            assert len(audits) == 2
            assert audits[-1].payload["result"]["scope"] == "human-session-track"
    finally:
        with original.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        repo.close()
