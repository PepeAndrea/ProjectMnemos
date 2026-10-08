"""Governed mutations: no biometric flag bypass, no write without its audit."""

from uuid import uuid4

import pytest
from mnemos.domain import Entity, Provenance, Retention
from mnemos.registry import GovernedRegistry
from mnemos.storage import EntityRepository, LocalActionRow
from sqlalchemy import event, select
from sqlalchemy.orm import Session


def sample():
    return Entity(
        kind="object",
        name="synthetic backpack",
        confidence=1,
        enrolled=True,
        provenance=Provenance(source_id="caller-claimed-source", method="synthetic"),
        retention=Retention(scope="persistent", purpose="manual enrollment"),
    )


def setup(tmp_path):
    repo = EntityRepository("sqlite:///" + str(tmp_path / "registry.db"))
    repo.initialize()
    return repo, GovernedRegistry(repo, uuid4())


def test_policy_audit_provenance_and_protected_fields(tmp_path):
    repo, registry = setup(tmp_path)
    original = sample()
    entity = registry.save(original)
    assert entity.owner_id == registry.owner_id
    assert entity.provenance.source_id == "owner-dashboard"
    entity.name = "owner corrected name"
    registry.save(entity, create=False)
    with Session(repo.engine) as session:
        audits = list(session.scalars(select(LocalActionRow)))
        assert len(audits) == 2
        assert all(row.payload["policy"]["allowed"] for row in audits)
        assert {row.payload["result"]["proposal"]["kind"] for row in audits} == {
            "entity_create",
            "entity_update",
        }
        assert "owner corrected name" not in str([row.payload for row in audits])
    for changes in (
        {"kind": "device"},
        {"owner_id": uuid4()},
        {"reference_ids": [uuid4()]},
        {"embedding_refs": [uuid4()]},
        {"retention": Retention(scope="persistent", purpose="expanded retention")},
    ):
        invalid = Entity.model_validate({**entity.model_dump(), **changes})
        with pytest.raises(PermissionError):
            registry.save(invalid, create=False)
    assert repo.get(entity.id).name == "owner corrected name"
    repo.close()


def test_consent_boolean_does_not_authorize_people_or_reference_injection(tmp_path):
    repo, registry = setup(tmp_path)
    for changes in (
        {"kind": "person", "biometric_consent": True},
        {"reference_ids": [uuid4()]},
        {"embedding_refs": [uuid4()]},
        {"owner_id": uuid4()},
    ):
        entity = Entity.model_validate({**sample().model_dump(), **changes})
        with pytest.raises(PermissionError):
            registry.save(entity)
    assert repo.list() == []
    with Session(repo.engine) as session:
        assert list(session.scalars(select(LocalActionRow))) == []
    repo.close()


def test_audit_failure_rolls_back_create_and_update(tmp_path):
    repo, registry = setup(tmp_path)
    entity = registry.save(sample())

    def fail(*args):
        raise RuntimeError("synthetic audit failure")

    event.listen(LocalActionRow, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError):
            registry.save(sample())
        entity.name = "must roll back"
        with pytest.raises(RuntimeError):
            registry.save(entity, create=False)
    finally:
        event.remove(LocalActionRow, "before_insert", fail)
    assert len(repo.list()) == 1
    assert repo.get(entity.id).name == "synthetic backpack"
    with Session(repo.engine) as session:
        assert len(list(session.scalars(select(LocalActionRow)))) == 1
    repo.close()


def test_policy_denial_prevents_database_write(tmp_path, monkeypatch):
    from mnemos.domain import ActionPolicyDecision, Risk

    repo, registry = setup(tmp_path)

    def deny(self, proposal, auth):
        return ActionPolicyDecision(
            proposal_id=proposal.id,
            allowed=False,
            risk=Risk.AUDIT,
            reason="synthetic denied owner",
            confirmation_required=False,
        )

    monkeypatch.setattr("mnemos.registry.PolicyEngine.evaluate", deny)
    with pytest.raises(PermissionError):
        registry.save(sample())
    assert repo.list() == []
    repo.close()


def test_real_postgres_governed_registry():
    import os

    from mnemos.storage import Base
    from sqlalchemy.schema import CreateSchema, DropSchema

    url = os.environ.get("MNEMOS_TEST_POSTGRES")
    if not url:
        pytest.skip("real PostgreSQL opt-in")
    repo = EntityRepository(url)
    schema = "test_registry_" + uuid4().hex
    with repo.engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    original_engine = repo.engine
    repo.engine = original_engine.execution_options(schema_translate_map={None: schema})
    try:
        Base.metadata.create_all(repo.engine)
        registry = GovernedRegistry(repo, uuid4())
        entity = registry.save(sample())
        entity.name = "PostgreSQL owner correction"
        registry.save(entity, create=False)
        assert repo.get(entity.id).name == entity.name
        with Session(repo.engine) as session:
            assert len(list(session.scalars(select(LocalActionRow)))) == 2
        with pytest.raises(ValueError):
            registry.save(entity)
        execution = registry.delete(entity.id, entity.name, True)
        assert execution.policy.allowed
        with pytest.raises(KeyError):
            repo.get(entity.id)
    finally:
        with original_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        repo.close()


def test_delete_strong_confirmation_dependencies_and_atomic_failure(tmp_path):
    repo, registry = setup(tmp_path)
    entity = registry.save(sample())
    for name, confirmation in ((entity.name, False), ("wrong current name", True)):
        with pytest.raises(PermissionError):
            registry.delete(entity.id, name, confirmation)
        assert repo.get(entity.id)
    related = sample()
    related.relations = {"owns": [entity.id]}
    repo.save(related)  # Legacy/internal fixture, not a permitted generic API write.
    with pytest.raises(PermissionError):
        registry.delete(entity.id, entity.name, True)
    related.relations = {}
    repo.save(related, create=False)

    def fail(*args):
        raise RuntimeError("synthetic delete audit failure")

    event.listen(LocalActionRow, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError):
            registry.delete(entity.id, entity.name, True)
    finally:
        event.remove(LocalActionRow, "before_insert", fail)
    assert repo.get(entity.id)
    execution = registry.delete(entity.id, entity.name, True)
    assert execution.policy.allowed and execution.policy.risk.value == "strong-confirmation"
    with pytest.raises(KeyError):
        repo.get(entity.id)
    with pytest.raises(KeyError):
        registry.delete(entity.id, entity.name, True)
    with Session(repo.engine) as session:
        assert len(list(session.scalars(select(LocalActionRow)))) == 2
    repo.close()


def test_delete_requires_dedicated_reference_and_person_revocation(tmp_path):
    repo, registry = setup(tmp_path)
    for changes in (
        {"kind": "person", "biometric_consent": True},
        {"reference_ids": [uuid4()]},
        {"embedding_refs": [uuid4()]},
        {"owner_id": uuid4()},
    ):
        entity = Entity.model_validate({**sample().model_dump(), **changes})
        repo.save(entity)  # Internal fixture for previously persisted protected enrollment.
        with pytest.raises(PermissionError):
            registry.delete(entity.id, entity.name, True)
        assert repo.get(entity.id) == entity
    with Session(repo.engine) as session:
        assert list(session.scalars(select(LocalActionRow))) == []
    repo.close()
