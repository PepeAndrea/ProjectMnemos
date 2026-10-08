"""Explicit, encrypted object crops. Files are never public/static media."""

import asyncio
import hmac
import json
import os
import secrets
import stat
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .biometrics import BiometricKey
from .domain import ActionExecution, ActionProposal, Entity, Provenance, Risk
from .policy import Authorization, PolicyEngine
from .runtime import RuntimeLayout
from .storage import EntityRepository, EntityRow, LocalActionRow
from .storage import ReferenceRow as ReferenceRow  # noqa: PLC0414 - preserve public model re-export


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class ObjectReferences:
    def __init__(self, repo: EntityRepository, owner: UUID, layout: RuntimeLayout):
        self.repo, self.owner = repo, owner
        self.folder = layout.path("media/evidence/object-references")
        self.key = BiometricKey(layout.path("data/security/reference-key"))
        self.lock = threading.RLock()
        self.stop_event = asyncio.Event()
        self.task: asyncio.Task[None] | None = None
        self.error: str | None = None
        self.row_type: type[ReferenceRow] = ReferenceRow
        self.audit_source = "owner-object-reference"
        self.requires_name = False

    def path(self, reference_id: UUID) -> Path:
        # UUID-derived paths only; no caller filenames or traversal.
        return self.folder / (str(reference_id) + ".enc")

    def list(self, entity_id: UUID) -> list[dict[str, Any]]:
        with self.lock, Session(self.repo.engine) as session:
            self.owner_entity(session, entity_id)
            rows = session.scalars(
                select(self.row_type)
                .where(
                    self.row_type.entity_id == str(entity_id),
                    self.row_type.payload["owner_id"].as_string() == str(self.owner),
                    self.row_type.payload["state"].as_string() == "active",
                    self.row_type.expires_at > datetime.now(UTC),
                )
                .order_by(self.row_type.expires_at, self.row_type.id)
                .limit(20)
            )
            return [
                {
                    "id": row.id,
                    "expires_at": aware(row.expires_at).isoformat(),
                    "observed_at": str(row.payload["provenance"].get("observed_at", "")),
                    "quality": row.payload["provenance"].get("quality"),
                }
                for row in rows
            ]

    def audit(
        self,
        session: Session,
        kind: Literal["reference_store", "reference_read", "reference_delete", "reference_expire"],
        reference_id: UUID,
        entity_id: UUID,
        *,
        confirmed: bool = False,
        denied: bool = False,
    ) -> None:
        proposal = ActionProposal(
            kind=kind,
            requested_by=self.owner,
            confidence=1,
            risk=Risk.AUDIT,
            source_event_id=uuid4(),
            params={"reference_id": str(reference_id), "entity_id": str(entity_id)},
            provenance=Provenance(source_id=self.audit_source, method="human"),
        )
        decision = PolicyEngine().evaluate(
            proposal,
            Authorization(self.owner, True, confirmation=confirmed, strong_confirmation=confirmed),
        )
        if not decision.allowed:
            raise PermissionError(decision.reason)
        execution = ActionExecution(
            proposal_id=proposal.id,
            status="denied" if denied else "succeeded",
            policy=decision,
            result={"proposal": proposal.model_dump(mode="json")},
        )
        session.add(
            LocalActionRow(
                id=str(proposal.id),
                created_at=execution.executed_at,
                payload=execution.model_dump(mode="json"),
            )
        )

    def owner_entity(
        self, session: Session, entity_id: UUID, *, allow_expired: bool = False
    ) -> EntityRow:
        row = session.scalar(
            select(EntityRow).where(EntityRow.id == str(entity_id)).with_for_update()
        )
        if row is None:
            raise KeyError(entity_id)
        entity = Entity.model_validate(row.payload)
        if entity.kind != "object" or entity.owner_id != self.owner or not entity.enrolled:
            raise PermissionError("enrolled owner object required")
        if (
            not allow_expired
            and entity.retention.expires_at
            and aware(entity.retention.expires_at) <= datetime.now(UTC)
        ):
            raise PermissionError("object retention expired")
        return row

    def reference_count(self, session: Session, entity: Entity) -> int:
        return len(entity.reference_ids)

    def attach(self, entity_row: EntityRow, entity: Entity, reference_id: UUID) -> None:
        entity.reference_ids.append(reference_id)
        entity_row.payload = entity.model_dump(mode="json")

    def payload_fields(self, session: Session, entity_row: EntityRow) -> dict[str, Any]:
        return {}

    def validate_reference(self, session: Session, row: ReferenceRow) -> None:
        pass

    def cleanup_entity(self, session: Session, row: ReferenceRow) -> EntityRow | None:
        return session.scalar(
            select(EntityRow).where(EntityRow.id == row.entity_id).with_for_update()
        )

    def store(
        self,
        entity_id: UUID,
        jpeg: bytes,
        provenance: dict[str, Any],
        expires_at: datetime,
        *,
        confirmed: bool,
        confirmed_name: str | None = None,
    ) -> UUID:
        if expires_at.tzinfo is None or expires_at <= datetime.now(UTC):
            raise ValueError("aware future reference expiry required")
        if not 0 < len(jpeg) <= 2 * 1024 * 1024 or not jpeg.startswith(b"\xff\xd8"):
            raise ValueError("bounded server-produced JPEG required")
        key = uuid4()
        path = self.path(key)
        written = False
        with self.lock:
            try:
                with Session(self.repo.engine) as session, session.begin():
                    entity_row = self.owner_entity(session, entity_id)
                    entity = Entity.model_validate(entity_row.payload)
                    if self.requires_name and entity_row.name != confirmed_name:
                        raise PermissionError("current person name confirmation required")
                    if self.reference_count(session, entity) >= 20:
                        raise ValueError("entity reference budget exceeded")
                    if entity.retention.expires_at and expires_at > aware(
                        entity.retention.expires_at
                    ):
                        raise PermissionError("reference cannot outlive entity retention")
                    self.audit(session, "reference_store", key, entity_id, confirmed=confirmed)
                    self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
                    self.folder.chmod(0o700)
                    files = list(self.folder.glob("*.enc"))
                    if (
                        len(files) >= 512
                        or sum(p.lstat().st_size for p in files) + len(jpeg) + 28 > 64 * 1024 * 1024
                    ):
                        raise ValueError("local reference storage budget exceeded")
                    existing = session.scalar(select(self.row_type.id).limit(1))
                    secret = self.key.load(create=not files and existing is None)
                    # Private, entity-bound tag avoids storing an offline-guessable
                    # public image hash. Existing pre-tag references remain readable.
                    content_tag = hmac.digest(secret, entity_id.bytes + jpeg, "sha256").hex()
                    duplicate = session.scalar(
                        select(self.row_type.id)
                        .where(
                            self.row_type.entity_id == str(entity_id),
                            self.row_type.payload["owner_id"].as_string() == str(self.owner),
                            self.row_type.payload["state"].as_string() == "active",
                            self.row_type.expires_at > datetime.now(UTC),
                            self.row_type.payload["content_tag"].as_string() == content_tag,
                        )
                        .limit(1)
                    )
                    if duplicate is not None:
                        raise ValueError(
                            "identical reference already saved; acquire a different view"
                        )
                    payload = {
                        "owner_id": str(self.owner),
                        "state": "active",
                        "provenance": provenance,
                        "expires_at": expires_at.isoformat(),
                        "mime": "image/jpeg",
                        "content_tag": content_tag,
                        **self.payload_fields(session, entity_row),
                    }
                    row = self.row_type(
                        id=str(key),
                        entity_id=str(entity_id),
                        expires_at=expires_at,
                        byte_count=len(jpeg) + 28,
                        payload=payload,
                    )
                    nonce = secrets.token_bytes(12)
                    sealed = nonce + AESGCM(secret).encrypt(nonce, jpeg, self.aad(row))
                    descriptor = os.open(
                        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
                    )
                    written = True
                    with os.fdopen(descriptor, "wb") as stream:
                        stream.write(sealed)
                        stream.flush()
                        os.fsync(stream.fileno())
                    session.add(row)
                    self.attach(entity_row, entity, key)
            except BaseException:
                if written:
                    path.unlink(missing_ok=True)
                raise
        return key

    def aad(self, row: ReferenceRow) -> bytes:
        # State changes are intentional deletion tombstones; other metadata is bound.
        return json.dumps(
            [
                "mnemos-object-reference-v1",
                row.id,
                row.entity_id,
                row.byte_count,
                {k: v for k, v in row.payload.items() if k != "state"},
            ],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

    def read(self, reference_id: UUID) -> bytes:
        denied = False
        data = b""
        with self.lock, Session(self.repo.engine) as session, session.begin():
            row = session.get(self.row_type, str(reference_id))
            if row is None or row.payload["owner_id"] != str(self.owner):
                raise KeyError(reference_id)
            try:
                self.owner_entity(session, UUID(row.entity_id))
                self.validate_reference(session, row)
                if aware(row.expires_at) != datetime.fromisoformat(row.payload["expires_at"]):
                    raise PermissionError("reference expiry metadata mismatch")
                if row.payload["state"] != "active" or aware(row.expires_at) <= datetime.now(UTC):
                    raise PermissionError("reference not active")
                descriptor = os.open(self.path(reference_id), os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(descriptor, "rb") as stream:
                    info = os.fstat(stream.fileno())
                    if (
                        not stat.S_ISREG(info.st_mode)
                        or info.st_uid != os.getuid()
                        or stat.S_IMODE(info.st_mode) != 0o600
                        or not 28 < info.st_size <= 2 * 1024 * 1024 + 28
                        or info.st_size != row.byte_count
                    ):
                        raise PermissionError("invalid private reference envelope")
                    sealed = stream.read(2 * 1024 * 1024 + 29)
                data = AESGCM(self.key.load()).decrypt(sealed[:12], sealed[12:], self.aad(row))
            except (OSError, ValueError, PermissionError, InvalidTag, KeyError):
                denied = True
            self.audit(session, "reference_read", reference_id, UUID(row.entity_id), denied=denied)
        if denied:
            raise PermissionError("reference unavailable or access denied")
        return data

    def retire(self, reference_id: UUID, confirmed_name: str, *, confirmed: bool) -> None:
        with self.lock, Session(self.repo.engine) as session, session.begin():
            row = session.scalar(
                select(self.row_type).where(self.row_type.id == str(reference_id)).with_for_update()
            )
            if row is None or row.payload["owner_id"] != str(self.owner):
                raise KeyError(reference_id)
            entity_row = self.owner_entity(session, UUID(row.entity_id), allow_expired=True)
            if entity_row.name != confirmed_name:
                raise PermissionError("current object name required")
            self.audit(
                session, "reference_delete", reference_id, UUID(row.entity_id), confirmed=confirmed
            )
            self.mark_deleted(entity_row, row)

    def mark_deleted(self, entity_row: EntityRow | None, row: ReferenceRow) -> None:
        if entity_row:
            entity = Entity.model_validate(entity_row.payload)
            entity.reference_ids = [key for key in entity.reference_ids if str(key) != row.id]
            entity_row.payload = entity.model_dump(mode="json")
        row.payload = {**row.payload, "state": "pending-deletion"}

    def cleanup(self) -> int:
        with self.lock:
            with Session(self.repo.engine) as session, session.begin():
                rows = session.scalars(
                    select(self.row_type)
                    .where(
                        self.row_type.expires_at <= datetime.now(UTC),
                        self.row_type.payload["state"].as_string() == "active",
                        self.row_type.payload["owner_id"].as_string() == str(self.owner),
                    )
                    .with_for_update(skip_locked=True)
                    .limit(100)
                )
                for row in rows:
                    self.audit(session, "reference_expire", UUID(row.id), UUID(row.entity_id))
                    entity_row = self.cleanup_entity(session, row)
                    self.mark_deleted(entity_row, row)
            count = 0
            with Session(self.repo.engine) as session, session.begin():
                rows = session.scalars(
                    select(self.row_type)
                    .where(
                        self.row_type.payload["state"].as_string() == "pending-deletion",
                        self.row_type.payload["owner_id"].as_string() == str(self.owner),
                    )
                    .with_for_update(skip_locked=True)
                    .limit(100)
                )
                for row in rows:
                    self.path(UUID(row.id)).unlink(missing_ok=True)
                    session.delete(row)
                    count += 1
            return count

    def start(self) -> None:
        self.task = asyncio.create_task(self.run())

    async def run(self) -> None:
        while not self.stop_event.is_set():
            try:
                await asyncio.to_thread(self.cleanup)
                self.error = None
            except (SQLAlchemyError, OSError, ValueError):
                self.error = "reference retention cleanup unavailable"
            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=1)
            except TimeoutError:
                pass

    async def stop(self) -> None:
        self.stop_event.set()
        if self.task:
            await self.task
