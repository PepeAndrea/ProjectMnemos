"""Synthetic vectors only; no real-person enrollment or biometric quality claim."""

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from mnemos.biometrics import BiometricKey, ConsentRow, PersonEnrollment, TemplateRow
from mnemos.storage import EntityRepository, LocalActionRow
from sqlalchemy import event, select
from sqlalchemy.orm import Session


def setup(tmp_path):
    repo = EntityRepository("sqlite:///" + str(tmp_path / "biometrics.db"))
    repo.initialize()
    service = PersonEnrollment(repo, uuid4(), BiometricKey(tmp_path / "security" / "key"))
    entity = service.grant(
        "Synthetic subject",
        face=True,
        voice=False,
        subject_permission_attested=True,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    consent_id = UUID(service.status(entity.id)["id"])
    return repo, service, entity, consent_id


def test_encryption_permissions_scope_access_audit_tamper_and_revocation(tmp_path):
    repo, service, entity, consent_id = setup(tmp_path)
    with pytest.raises(PermissionError):
        service.store(consent_id, "voice", (1.0, 0.0), "synthetic", confirmed=True)
    with pytest.raises(PermissionError):
        service.store(consent_id, "face", (1.0, 0.0), "synthetic", confirmed=False)
    key = service.store(consent_id, "face", (1.0, 0.0), "synthetic-v1", confirmed=True)
    assert service.read(key) == (1.0, 0.0)
    assert service.key.path.stat().st_mode & 0o777 == 0o600
    with Session(repo.engine) as session, session.begin():
        row = session.get(TemplateRow, str(key))
        assert row.ciphertext != b"\x00\x00\x80?\x00\x00\x00\x00"
        row.provider = "swapped-model"
    with pytest.raises(PermissionError):
        service.read(key)
    with pytest.raises(PermissionError):
        service.revoke(entity.id, "wrong name", confirmed=True)
    service.revoke(entity.id, entity.name, confirmed=True)
    with pytest.raises(KeyError):
        repo.get(entity.id)
    with pytest.raises(KeyError):
        service.read(key)
    assert service.status(entity.id)["status"] == "revoked"
    with Session(repo.engine) as session:
        assert list(session.scalars(select(TemplateRow))) == []
        audits = list(session.scalars(select(LocalActionRow)))
        assert any(row.payload["status"] == "denied" for row in audits)
        assert "Synthetic subject" not in str([row.payload for row in audits])
    repo.close()


def test_missing_or_insecure_key_never_replaces_existing_ciphertext(tmp_path):
    repo, service, _entity, consent_id = setup(tmp_path)
    key = service.store(consent_id, "face", (1.0, 0.0), "synthetic", confirmed=True)
    original = service.key.path.read_bytes()
    service.key.path.chmod(0o644)
    with pytest.raises(PermissionError):
        service.read(key)
    service.key.path.chmod(0o600)
    service.key.path.unlink()
    with pytest.raises(FileNotFoundError):
        service.store(consent_id, "face", (0.0, 1.0), "synthetic", confirmed=True)
    assert not service.key.path.exists()
    service.key.path.write_bytes(original)
    service.key.path.chmod(0o600)
    assert service.read(key) == (1.0, 0.0)
    repo.close()


def test_expiry_and_revoke_failure_are_atomic(tmp_path):
    repo, service, entity, consent_id = setup(tmp_path)
    key = service.store(consent_id, "face", (1.0, 0.0), "synthetic", confirmed=True)

    def fail(*args):
        raise RuntimeError("synthetic audit failure")

    event.listen(LocalActionRow, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError):
            service.revoke(entity.id, entity.name, confirmed=True)
    finally:
        event.remove(LocalActionRow, "before_insert", fail)
    assert service.read(key) == (1.0, 0.0)
    with Session(repo.engine) as session, session.begin():
        session.get(ConsentRow, str(consent_id)).expires_at = datetime.now(UTC) - timedelta(
            seconds=1
        )
    with pytest.raises(PermissionError):
        service.read(key)
    assert service.people() == []
    assert service.status(entity.id)["status"] == "expired"
    assert service.status(entity.id)["cleanup_pending"] is True
    event.listen(LocalActionRow, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError):
            service.purge_expired()
    finally:
        event.remove(LocalActionRow, "before_insert", fail)
    assert repo.get(entity.id).id == entity.id
    assert service.people() == []
    assert service.purge_expired() == 1
    assert service.status(entity.id)["cleanup_pending"] is False
    assert service.purge_expired() == 0
    with pytest.raises(KeyError):
        repo.get(entity.id)
    with Session(repo.engine) as session:
        assert list(session.scalars(select(TemplateRow))) == []
    repo.close()


@pytest.mark.skipif(not os.environ.get("MNEMOS_TEST_POSTGRES"), reason="real PostgreSQL opt-in")
def test_postgres_encrypted_store_revoke(tmp_path):
    from mnemos.storage import Base
    from sqlalchemy.schema import CreateSchema, DropSchema

    repo = EntityRepository(os.environ["MNEMOS_TEST_POSTGRES"])
    original = repo.engine
    schema = "test_biometrics_" + uuid4().hex
    with original.begin() as connection:
        connection.execute(CreateSchema(schema))
    repo.engine = original.execution_options(schema_translate_map={None: schema})
    try:
        Base.metadata.create_all(repo.engine)
        service = PersonEnrollment(repo, uuid4(), BiometricKey(tmp_path / "private" / "key"))
        entity = service.grant(
            "Synthetic PG subject",
            face=True,
            voice=True,
            subject_permission_attested=True,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        consent_id = UUID(service.status(entity.id)["id"])
        key = service.store(consent_id, "voice", (1.0, 0.0, 0.0), "synthetic", confirmed=True)
        assert service.read(key) == (1.0, 0.0, 0.0)
        service.revoke(entity.id, entity.name, confirmed=True)
        with pytest.raises(KeyError):
            service.read(key)
    finally:
        with original.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        repo.close()


def test_expiry_batches_do_not_starve_behind_already_expired_metadata(tmp_path):
    from sqlalchemy import update

    repo = EntityRepository("sqlite:///" + str(tmp_path / "expiry-batches.db"))
    repo.initialize()
    service = PersonEnrollment(repo, uuid4(), BiometricKey(tmp_path / "private" / "key"))
    for _ in range(101):
        service.grant(
            "Synthetic expiration batch",
            face=True,
            voice=False,
            subject_permission_attested=True,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
    with repo.engine.begin() as connection:
        connection.execute(
            update(ConsentRow).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    assert service.purge_expired() == 100
    assert service.purge_expired() == 1
    assert service.purge_expired() == 0
    assert repo.list() == []
    repo.close()
