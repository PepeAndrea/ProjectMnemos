"""Local consent-bound encrypted vectors. No client vector or cloud interface."""

import asyncio
import json
import math
import os
import secrets
import stat
import struct
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import JSON, DateTime, Integer, LargeBinary, String, delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Mapped, Session, mapped_column

from .domain import ActionExecution, ActionProposal, Entity, Provenance, Retention, Risk
from .policy import Authorization, PolicyEngine
from .storage import Base, EntityRepository, EntityRow, FaceReferenceRow, LocalActionRow


class ConsentRow(Base):
    __tablename__ = "person_consents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(36), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class TemplateRow(Base):
    __tablename__ = "biometric_templates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    consent_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(8))
    provider: Mapped[str] = mapped_column(String(256))
    dimensions: Mapped[int] = mapped_column(Integer)
    nonce: Mapped[bytes] = mapped_column(LargeBinary)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)


class BiometricKey:
    def __init__(self, path: Path):
        self.path = path

    def load(self, *, create: bool = False) -> bytes:
        if create:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.path.parent.chmod(0o700)
            try:
                descriptor = os.open(
                    self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
                )
            except FileExistsError:
                pass
            else:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(secrets.token_bytes(32))
                    stream.flush()
                    os.fsync(stream.fileno())
        descriptor = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
            ):
                raise PermissionError("biometric key requires private owner-only regular file")
            value = stream.read(33)
        if len(value) != 32:
            raise ValueError("invalid biometric key; restore the original key without replacing it")
        return value


def aad(row: TemplateRow) -> bytes:
    return json.dumps(
        ["mnemos-biometric-v1", row.id, row.consent_id, row.kind, row.provider, row.dimensions],
        separators=(",", ":"),
    ).encode()


class PersonEnrollment:
    def __init__(self, repository: EntityRepository, owner_id: UUID, key: BiometricKey):
        self.repository, self.owner_id, self.key = repository, owner_id, key
        self.task: asyncio.Task[None] | None = None
        self.stop_event = asyncio.Event()
        self.cleanup_error: str | None = None

    def audit(
        self,
        session: Session,
        kind: Literal[
            "person_enroll",
            "person_revoke",
            "biometric_store",
            "biometric_read",
            "consent_expire",
            "entity_update",
        ],
        params: dict[str, Any],
        *,
        confirmed: bool = False,
        allowed: bool = True,
    ) -> None:
        proposal = ActionProposal(
            kind=kind,
            params=params,
            source_event_id=uuid4(),
            requested_by=self.owner_id,
            confidence=1,
            risk=Risk.AUDIT,
            provenance=Provenance(source_id="owner-person-enrollment", method="human"),
        )
        decision = PolicyEngine().evaluate(
            proposal,
            Authorization(
                self.owner_id, True, confirmation=confirmed, strong_confirmation=confirmed
            ),
        )
        if not decision.allowed:
            raise PermissionError(decision.reason)
        execution = ActionExecution(
            proposal_id=proposal.id,
            status="succeeded" if allowed else "denied",
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

    def grant(
        self,
        name: str,
        *,
        face: bool,
        voice: bool,
        subject_permission_attested: bool,
        expires_at: datetime,
        entity_id: UUID | None = None,
        reviewed_proposal_id: UUID | None = None,
    ) -> Entity:
        if not name.strip() or not (face or voice) or not subject_permission_attested:
            raise PermissionError(
                "explicit subject permission and separate recognition scope required"
            )
        if expires_at.tzinfo is None or expires_at <= datetime.now(UTC):
            raise ValueError("consent expiry must be an aware future timestamp")
        entity = Entity(
            id=entity_id or uuid4(),
            kind="person",
            name=name.strip(),
            enrolled=True,
            biometric_consent=True,
            owner_id=self.owner_id,
            confidence=1,
            provenance=Provenance(
                source_id="owner-reviewed-person-consent"
                if reviewed_proposal_id
                else "owner-attested-person-consent",
                method="human",
            ),
            retention=Retention(
                scope="persistent",
                purpose="explicit local person enrollment",
                expires_at=expires_at,
            ),
        )
        consent_id = uuid4()
        with Session(self.repository.engine) as session, session.begin():
            if session.get(EntityRow, str(entity.id)) is not None:
                raise ValueError("entity already registered; refresh catalog before retry")
            session.add(
                EntityRow(
                    id=str(entity.id),
                    kind=entity.kind,
                    name=entity.name,
                    payload=entity.model_dump(mode="json"),
                )
            )
            session.add(
                ConsentRow(
                    id=str(consent_id),
                    entity_id=str(entity.id),
                    expires_at=expires_at,
                    payload={
                        "owner_id": str(self.owner_id),
                        "face": face,
                        "voice": voice,
                        "status": "active",
                        "assurance": "owner-attested-subject-permission",
                        "policy_version": "local-person-consent-v1",
                        "granted_at": datetime.now(UTC).isoformat(),
                    },
                )
            )
            self.audit(
                session,
                "person_enroll",
                {
                    "entity_id": str(entity.id),
                    "consent_id": str(consent_id),
                    "face": face,
                    "voice": voice,
                    "expires_at": expires_at.isoformat(),
                    **(
                        {"reviewed_proposal_id": str(reviewed_proposal_id)}
                        if reviewed_proposal_id
                        else {}
                    ),
                },
                confirmed=True,
            )
        return entity

    def consent(self, session: Session, consent_id: str) -> ConsentRow:
        row = session.scalar(
            select(ConsentRow).where(ConsentRow.id == consent_id).with_for_update()
        )
        if row is None:
            raise KeyError(consent_id)
        at = row.expires_at
        if at.tzinfo is None:  # SQLite isolated tests normalize stored UTC.
            at = at.replace(tzinfo=UTC)
        if (
            row.payload["owner_id"] != str(self.owner_id)
            or row.payload["status"] != "active"
            or at <= datetime.now(UTC)
        ):
            raise PermissionError("active owner-authorized consent required")
        return row

    def status(self, entity_id: UUID) -> dict[str, Any]:
        with Session(self.repository.engine) as session:
            row = session.scalar(select(ConsentRow).where(ConsentRow.entity_id == str(entity_id)))
            if row is None or row.payload["owner_id"] != str(self.owner_id):
                raise KeyError(entity_id)
            expiry = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
            pending = row.payload["status"] == "active" and expiry <= datetime.now(UTC)
            return {
                "id": row.id,
                "entity_id": row.entity_id,
                "expires_at": expiry.isoformat(),
                **row.payload,
                "status": "expired" if pending else row.payload["status"],
                "cleanup_pending": pending,
            }

    def store(
        self,
        consent_id: UUID,
        kind: Literal["face", "voice"],
        vector: tuple[float, ...],
        provider: str,
        *,
        confirmed: bool,
    ) -> UUID:
        if (
            not 1 <= len(vector) <= 4096
            or not all(math.isfinite(value) for value in vector)
            or not 0 < len(provider) <= 256
        ):
            raise ValueError("invalid local provider vector")
        norm = math.sqrt(sum(value * value for value in vector))
        if not math.isfinite(norm) or norm <= 0:
            raise ValueError("invalid vector norm")
        packed = struct.pack("<" + "f" * len(vector), *(value / norm for value in vector))
        template_id = uuid4()
        with Session(self.repository.engine) as session, session.begin():
            consent = self.consent(session, str(consent_id))
            if not consent.payload[kind]:
                raise PermissionError("recognition scope not granted")
            self.audit(
                session,
                "biometric_store",
                {"template_id": str(template_id), "consent_id": consent.id},
                confirmed=confirmed,
            )
            count = len(
                list(
                    session.scalars(
                        select(TemplateRow.id)
                        .where(TemplateRow.consent_id == consent.id, TemplateRow.kind == kind)
                        .limit(20)
                    )
                )
            )
            if count >= 20:
                raise ValueError("template count budget exceeded")
            existing = session.scalar(select(TemplateRow.id).limit(1))
            key = self.key.load(create=existing is None)
            row = TemplateRow(
                id=str(template_id),
                consent_id=consent.id,
                kind=kind,
                provider=provider,
                dimensions=len(vector),
                nonce=secrets.token_bytes(12),
            )
            row.ciphertext = AESGCM(key).encrypt(row.nonce, packed, aad(row))
            session.add(row)
        return template_id

    def read(self, template_id: UUID) -> tuple[float, ...]:
        denied = False
        missing = False
        value: tuple[float, ...] = ()
        with Session(self.repository.engine) as session, session.begin():
            row = session.get(TemplateRow, str(template_id))
            if row is None:
                denied = missing = True
            else:
                try:
                    self.consent(session, row.consent_id)
                    if (
                        not 1 <= row.dimensions <= 4096
                        or len(row.nonce) != 12
                        or len(row.ciphertext) != row.dimensions * 4 + 16
                    ):
                        raise ValueError("invalid encrypted vector envelope")
                    packed = AESGCM(self.key.load()).decrypt(row.nonce, row.ciphertext, aad(row))
                    value = struct.unpack("<" + "f" * row.dimensions, packed)
                except (PermissionError, InvalidTag, ValueError, OSError, struct.error):
                    denied = True
            self.audit(
                session, "biometric_read", {"template_id": str(template_id)}, allowed=not denied
            )
        if missing:
            raise KeyError(template_id)
        if denied:
            raise PermissionError("biometric access denied or encrypted data unavailable")
        return value

    def revoke(self, entity_id: UUID, confirmed_name: str, *, confirmed: bool) -> None:
        with Session(self.repository.engine) as session, session.begin():
            row = session.scalar(
                select(ConsentRow).where(ConsentRow.entity_id == str(entity_id)).with_for_update()
            )
            entity = session.get(EntityRow, str(entity_id))
            if row is None or entity is None:
                raise KeyError(entity_id)
            if row.payload["owner_id"] != str(self.owner_id) or entity.name != confirmed_name:
                raise PermissionError("owner and current-name confirmation required")
            self.audit(
                session,
                "person_revoke",
                {"entity_id": str(entity_id), "consent_id": row.id},
                confirmed=confirmed,
            )
            session.execute(delete(TemplateRow).where(TemplateRow.consent_id == row.id))
            self.retire_face_references(session, row.entity_id)
            session.delete(entity)
            row.payload = {
                **row.payload,
                "status": "revoked",
                "revoked_at": datetime.now(UTC).isoformat(),
            }

    def purge_expired(self) -> int:
        count = 0
        with Session(self.repository.engine) as session, session.begin():
            rows = session.scalars(
                select(ConsentRow)
                .where(
                    ConsentRow.expires_at <= datetime.now(UTC),
                    ConsentRow.payload["status"].as_string() == "active",
                    ConsentRow.payload["owner_id"].as_string() == str(self.owner_id),
                )
                .with_for_update(skip_locked=True)
                .limit(100)
            )
            for row in rows:
                if row.payload["status"] != "active" or row.payload["owner_id"] != str(
                    self.owner_id
                ):
                    continue
                self.audit(
                    session, "consent_expire", {"entity_id": row.entity_id, "consent_id": row.id}
                )
                session.execute(delete(TemplateRow).where(TemplateRow.consent_id == row.id))
                self.retire_face_references(session, row.entity_id)
                session.execute(delete(EntityRow).where(EntityRow.id == row.entity_id))
                row.payload = {**row.payload, "status": "expired"}
                count += 1
        return count

    def retire_face_references(self, session: Session, entity_id: str) -> None:
        rows = session.scalars(
            select(FaceReferenceRow)
            .where(
                FaceReferenceRow.entity_id == entity_id,
                FaceReferenceRow.payload["owner_id"].as_string() == str(self.owner_id),
                FaceReferenceRow.payload["state"].as_string() == "active",
            )
            .with_for_update()
        )
        for row in rows:
            row.payload = {**row.payload, "state": "pending-deletion"}

    def start(self) -> None:
        self.task = asyncio.create_task(self.run_cleanup())

    async def run_cleanup(self) -> None:
        while not self.stop_event.is_set():
            try:
                await asyncio.to_thread(self.purge_expired)
                self.cleanup_error = None
            except SQLAlchemyError:
                self.cleanup_error = "person retention cleanup database unavailable"
            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=1)
            except TimeoutError:
                pass

    async def stop(self) -> None:
        self.stop_event.set()
        if self.task:
            await self.task

    def rename(self, entity_id: UUID, name: str) -> Entity:
        if not name.strip():
            raise ValueError("person name must not be blank")
        with Session(self.repository.engine) as session, session.begin():
            consent = session.scalar(
                select(ConsentRow).where(ConsentRow.entity_id == str(entity_id))
            )
            if consent is None:
                raise KeyError(entity_id)
            self.consent(session, consent.id)
            row = session.get(EntityRow, str(entity_id))
            if row is None:
                raise KeyError(entity_id)
            value = Entity.model_validate({**row.payload, "name": name.strip()})
            self.audit(session, "entity_update", {"entity_id": str(entity_id)})
            row.name, row.payload = value.name, value.model_dump(mode="json")
        return value

    def people(self, limit: int = 100) -> list[dict[str, Any]]:
        if not 1 <= limit <= 1000:
            raise ValueError("invalid query limit")
        with Session(self.repository.engine) as session:
            rows = session.execute(
                select(EntityRow, ConsentRow)
                .join(ConsentRow, ConsentRow.entity_id == EntityRow.id)
                .where(
                    ConsentRow.payload["owner_id"].as_string() == str(self.owner_id),
                    ConsentRow.payload["status"].as_string() == "active",
                    ConsentRow.expires_at > datetime.now(UTC),
                )
                .order_by(EntityRow.name, EntityRow.id)
                .limit(limit)
            )
            return [
                {
                    "id": entity.id,
                    "name": entity.name,
                    "face": consent.payload["face"],
                    "voice": consent.payload["voice"],
                    "assurance": consent.payload["assurance"],
                    "expires_at": (
                        consent.expires_at
                        if consent.expires_at.tzinfo
                        else consent.expires_at.replace(tzinfo=UTC)
                    ).isoformat(),
                }
                for entity, consent in rows
            ]
