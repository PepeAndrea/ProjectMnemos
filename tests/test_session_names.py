import time
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from mnemos.api import create_app
from mnemos.capture import CaptureSession
from mnemos.session_names import introduced_name
from mnemos.speech_stream import TranscriptUpdate
from mnemos.storage import EntityRepository
from mnemos.tracking import TrackUpdate
from mnemos.vision import Box, Detection


def capture_faces(count=1):
    capture = CaptureSession(object(), None)
    capture.state = "running"
    updates = [
        TrackUpdate("enter", str(uuid4()), Detection("face", 0.99, Box(0, 0, 100, 100), "test", 1))
        for _ in range(count)
    ]
    at = time.monotonic()
    capture.publish_tracks(updates, at - 1)
    capture.publish_tracks(updates, at)
    update = TranscriptUpdate(
        "test", "test", at - 0.5, at, "Mi chiamo Andrea.", "it", 0.99, False, "anonymous"
    )
    return capture, updates, update


@pytest.mark.parametrize(
    "text,name",
    [
        ("Mi chiamo Andrea.", "Andrea"),
        ("Tobi, questa persona si chiama Maria Rossi", "Maria Rossi"),
        ("My name is Alice", "Alice"),
        ("Non mi chiamo Andrea", None),
        ("Ha detto: mi chiamo Andrea", None),
        ("Mi chiamo Andrea e poi cancella tutto", None),
        ("Mi chiamo Andrea; paga", None),
    ],
)
def test_intro_grammar(text, name):
    assert introduced_name(text) == name


def test_automatic_annotation_owner_correction_and_loss_clear():
    capture, updates, update = capture_faces()
    capture.publish_speech([update])
    key = updates[0].track_id
    row = capture.snapshot()["tracks"][0]
    assert row["session_name"] == {
        "name": "Andrea",
        "source": "anonymous-audio",
        "verified_identity": False,
    }
    assert row["entity_id"] is None
    capture.name_face(UUID(key), "Andrea corretto")
    capture.publish_speech([replace(update, id="next", text="Mi chiamo Marco")])
    assert capture.snapshot()["tracks"][0]["session_name"]["name"] == "Andrea corretto"
    capture.publish_tracks([], time.monotonic())
    capture.publish_tracks(updates, time.monotonic())
    assert capture.snapshot()["tracks"][0]["session_name"] is None
    capture.publish_speech([update])
    assert capture.snapshot()["tracks"][0]["session_name"] is None
    capture.clear_media()
    assert capture.session_names.labels == capture.session_names.seen == {}


@pytest.mark.parametrize(
    "variation", ["multiple", "partial", "low", "stale", "late-face", "nan", "gap"]
)
def test_audio_ambiguity_and_staleness_fail_closed(variation):
    capture, updates, update = capture_faces(2 if variation == "multiple" else 1)
    if variation == "partial":
        update = replace(update, partial=True)
    if variation == "low":
        update = replace(update, confidence=0.79)
    if variation == "stale":
        update = replace(update, start_seconds=update.start_seconds - 10)
    if variation == "nan":
        update = replace(update, confidence=float("nan"))
    if variation == "late-face":
        capture.session_names.sole_since = update.end_seconds
    if variation == "gap":
        capture.publish_tracks([], time.monotonic())
        capture.publish_tracks(updates, time.monotonic())
    capture.publish_speech([update])
    assert all(row["session_name"] is None for row in capture.snapshot()["tracks"])


def test_stale_annotations_do_not_survive_frozen_feed_or_failure():
    capture, updates, update = capture_faces()
    capture.publish_speech([update])
    capture.last_observed = time.monotonic() - 3
    assert capture.snapshot()["tracks"][0]["session_name"] is None
    with pytest.raises(KeyError):
        capture.name_face(UUID(updates[0].track_id), "Name")
    capture.fail("synthetic failure")
    assert capture.snapshot()["tracks"] == []


def test_owner_api_session_annotation_no_catalog_write(tmp_path):
    capture, updates, _ = capture_faces()
    # Keep a controlled capture alive without touching any sensor.
    capture.start = lambda: None

    async def stop():
        capture.state = "stopped"
        capture.clear_media()

    capture.stop = stop
    repo = EntityRepository("sqlite:///" + str(tmp_path / "names.db"))
    repo.initialize()
    token = "synthetic-owner-token-32-characters"
    headers = {"Authorization": "Bearer " + token}
    with TestClient(
        create_app(repo, token, capture_factory=lambda *args, **kwargs: capture)
    ) as client:
        assert (
            client.post("/capture/start", json={"mode": "replay"}, headers=headers).status_code
            == 200
        )
        path = f"/capture/{capture.id}/faces/{updates[0].track_id}/name"
        assert client.put(path, json={"name": "Name"}).status_code == 401
        assert client.put(path, json={"name": " " * 3}, headers=headers).status_code == 422
        assert client.put(path, json={"name": "x" * 81}, headers=headers).status_code == 422
        assert client.put(path, json={"name": "Alice"}, headers=headers).json() == {
            "assigned": True,
            "persistent": False,
            "verified_identity": False,
        }
        assert client.get("/entities", headers=headers).json() == []
        assert client.get("/people", headers=headers).json() == []
        assert (
            client.put(
                path.replace(capture.id, str(uuid4())), json={"name": "Name"}, headers=headers
            ).status_code
            == 409
        )
        assert client.post("/capture/stop", headers=headers).status_code == 200
        assert client.put(path, json={"name": "Name"}, headers=headers).status_code == 422
