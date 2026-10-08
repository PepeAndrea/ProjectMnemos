import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from mnemos.domain import (
    ActionProposal,
    Entity,
    Provenance,
    Reminder,
    Retention,
    Risk,
    Trigger,
    Utterance,
)
from mnemos.policy import Authorization, PolicyEngine
from mnemos.runtime import BoundedQueue, MediaChunk, RollingBuffer, RuntimeLayout
from mnemos.triggers import ready
from pydantic import ValidationError


def provenance():
    return Provenance(source_id="fixture", method="human")


def test_persistent_unknown_person_denied():
    with pytest.raises(ValidationError):
        Entity(
            kind="person",
            name="unknown",
            confidence=0.99,
            provenance=provenance(),
            retention=Retention(scope="persistent", purpose="identity"),
        )
    entity = Entity(
        kind="person",
        name="Andrea",
        confidence=1,
        provenance=provenance(),
        retention=Retention(scope="persistent", purpose="identity"),
        enrolled=True,
        biometric_consent=True,
    )
    assert Entity.model_validate_json(entity.model_dump_json()) == entity
    with pytest.raises(ValidationError):
        Entity.model_validate({**entity.model_dump(), "face_embedding": [1, 2]})


@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), float("inf")])
def test_scores_bounded(value):
    with pytest.raises(ValidationError):
        Entity(
            kind="object",
            name="zaino",
            confidence=value,
            provenance=provenance(),
            retention=Retention(purpose="session"),
        )


def test_timecode_and_partial_audio_boundaries():
    kwargs = {
        "conversation_id": uuid4(),
        "speaker_session_id": "A",
        "text": "ciao",
        "language": "it",
        "confidence": 0.9,
        "provenance": provenance(),
        "start_seconds": 2,
        "end_seconds": 1,
    }
    with pytest.raises(ValidationError):
        Utterance(**kwargs)
    kwargs["end_seconds"] = 3
    with pytest.raises(ValidationError):
        Utterance(**kwargs, source_audio_id=uuid4())


def test_containment_and_symlink(tmp_path):
    layout = RuntimeLayout(tmp_path)
    layout.path("tmp").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "runtime" / "link").symlink_to(outside)
    for name in ["../outside", "/tmp/outside", "link/secret", "."]:
        with pytest.raises(ValueError):
            layout.path(name)


def test_buffers_bounded_and_nonpersistent():
    buffer = RollingBuffer(seconds=5, max_bytes=6)
    for n in range(100):
        buffer.append(MediaChunk(n, b"abc"))
        assert buffer.bytes_used <= 6
    assert [c.timestamp for c in buffer.extract(98, 100)] == [98, 99]
    with pytest.raises(ValueError):
        buffer.append(MediaChunk(0, b"abc"))
    buffer.append(MediaChunk(110, b"oversized"))
    assert buffer.bytes_used == 0
    buffer.clear()
    assert not buffer.chunks


def test_queue_backpressure():
    queue = BoundedQueue[int](2)
    for n in range(100):
        queue.put(n)
    assert queue.dropped == 98
    assert queue.queue.get_nowait() == 98
    queue.queue.task_done()
    assert queue.queue.get_nowait() == 99
    queue.queue.task_done()
    asyncio.run(queue.queue.join())


def test_idle_buffer_expiration_and_tiny_chunk_overhead_are_bounded():
    buffer = RollingBuffer(seconds=5, max_bytes=1024, max_chunks=3)
    for _ in range(1000):
        buffer.append(MediaChunk(10, b"x"))
        buffer.append(MediaChunk(10, b""))
    assert buffer.bytes_used == len(buffer.chunks) == 3
    buffer.expire(16)
    assert buffer.bytes_used == 0 and not buffer.chunks
    with pytest.raises(ValueError):
        buffer.expire(float("nan"))


def test_spoofed_low_risk_does_not_bypass_confirmation():
    owner = uuid4()
    proposal = ActionProposal(
        kind="delete",
        params={},
        source_event_id=uuid4(),
        requested_by=owner,
        confidence=1,
        risk=Risk.AUTOMATIC,
        provenance=provenance(),
    )
    engine = PolicyEngine()
    assert not engine.evaluate(proposal, Authorization(owner, True)).allowed
    assert engine.evaluate(proposal, Authorization(owner, True, strong_confirmation=True)).allowed
    assert not engine.evaluate(
        proposal, Authorization(owner, False, speaker_id=uuid4(), speaker_confidence=1)
    ).allowed


def test_temporal_and_compound_trigger():
    at = datetime.now(UTC)
    entity = uuid4()
    reminder = Reminder(
        text="chiedi API",
        provenance=provenance(),
        trigger=Trigger(due_at=at, entity_visible=entity, place="ufficio"),
    )
    assert not ready(reminder, at, {entity}, place="casa")
    assert ready(reminder, at, {entity}, place="ufficio")
    reminder.state = "notified"
    assert not ready(reminder, at + timedelta(days=1), {entity}, place="ufficio")


def test_identity_template_refs_need_consent():
    from mnemos.domain import IdentityEntity

    with pytest.raises(ValidationError):
        IdentityEntity(
            name="unknown",
            confidence=0.9,
            provenance=provenance(),
            retention=Retention(purpose="session"),
            face_template_ids=[uuid4()],
        )
