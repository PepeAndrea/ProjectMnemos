"""Relational entity registry. SQLite is only used in isolated contract tests."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .domain import Entity


class Base(DeclarativeBase):
    pass


class EntityRow(Base):
    __tablename__ = "entities"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(4096), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class LocalActionRow(Base):
    __tablename__ = "local_action_audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class ReferenceRow(Base):
    __tablename__ = "object_references"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    byte_count: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class FaceReferenceRow(ReferenceRow):
    __tablename__ = "face_references"
    __mapper_args__ = {"concrete": True}  # noqa: RUF012 - SQLAlchemy declarative mapper config
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    byte_count: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class EntityRepository:
    def __init__(self, url: str):
        self.engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 5, "options": "-c statement_timeout=5000"}
            if url.startswith("postgresql")
            else {},
        )

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)

    def save(self, entity: Entity, *, create: bool = True) -> Entity:
        # Never promote anonymous person session tracks to persistent storage.
        if entity.retention.scope != "persistent":
            raise ValueError("session entities must remain in hot memory")
        with Session(self.engine) as session, session.begin():
            row = session.get(EntityRow, str(entity.id))
            if create and row is not None:
                raise ValueError("entity already exists")
            if not create and row is None:
                raise KeyError(entity.id)
            if row is None:
                row = EntityRow(id=str(entity.id))
                session.add(row)
            row.kind, row.name = entity.kind, entity.name
            row.payload = entity.model_dump(mode="json")
        return entity

    def get(self, entity_id: UUID) -> Entity:
        with Session(self.engine) as session:
            row = session.get(EntityRow, str(entity_id))
            if row is None:
                raise KeyError(entity_id)
            return Entity.model_validate(row.payload)

    def list(self, limit: int = 100) -> list[Entity]:
        if not 1 <= limit <= 1000:
            raise ValueError("invalid query limit")
        with Session(self.engine) as session:
            rows = session.scalars(
                select(EntityRow).order_by(EntityRow.name, EntityRow.id).limit(limit)
            )
            return [Entity.model_validate(row.payload) for row in rows]

    def close(self) -> None:
        self.engine.dispose()
