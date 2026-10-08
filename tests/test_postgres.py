"""Opt-in real infrastructure integration; never pretends SQLite validates pgvector."""

import os
from uuid import uuid4

import pytest
from mnemos.domain import Entity, Provenance, Retention
from mnemos.storage import EntityRepository
from sqlalchemy import text


@pytest.mark.skipif(
    not os.environ.get("MNEMOS_TEST_POSTGRES"), reason="PostgreSQL integration opt-in"
)
def test_real_registry_and_pgvector():
    repo = EntityRepository(os.environ["MNEMOS_TEST_POSTGRES"])
    entity = Entity(
        kind="object",
        name="synthetic-integration-" + str(uuid4()),
        confidence=1,
        enrolled=True,
        provenance=Provenance(source_id="test", method="synthetic"),
        retention=Retention(scope="persistent", purpose="integration fixture"),
    )
    try:
        repo.save(entity)
        assert repo.get(entity.id) == entity
        with repo.engine.connect() as connection:
            assert (
                connection.execute(text("SELECT '[1,0]'::vector <-> '[0,1]'::vector")).scalar() > 1
            )
    finally:
        with repo.engine.begin() as connection:
            connection.execute(text("DELETE FROM entities WHERE id = :id"), {"id": str(entity.id)})
        repo.close()
