"""Dedicated local face images with modality consent checked inside each transaction."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .biometrics import BiometricKey, ConsentRow
from .domain import Entity
from .references import ObjectReferences, ReferenceRow, aware
from .runtime import RuntimeLayout
from .storage import EntityRepository, EntityRow, FaceReferenceRow


class FaceReferences(ObjectReferences):
    def __init__(self, repo: EntityRepository, owner: UUID, layout: RuntimeLayout):
        super().__init__(repo, owner, layout)
        self.row_type = FaceReferenceRow
        self.folder = layout.path("media/evidence/face-references")
        self.key = BiometricKey(layout.path("data/security/face-reference-key"))
        self.audit_source = "owner-face-reference"
        self.requires_name = True

    def owner_entity(
        self, session: Session, entity_id: UUID, *, allow_expired: bool = False
    ) -> EntityRow:
        # Consent before entity/reference locks, matching consent revocation order.
        consent = session.scalar(
            select(ConsentRow).where(ConsentRow.entity_id == str(entity_id)).with_for_update()
        )
        if consent is None or consent.payload["owner_id"] != str(self.owner):
            raise KeyError(entity_id)
        if (
            not consent.payload["face"]
            or consent.payload["status"] != "active"
            or consent.payload["assurance"] != "owner-attested-subject-permission"
            or (not allow_expired and aware(consent.expires_at) <= datetime.now(UTC))
        ):
            raise PermissionError("active subject face consent required")
        row = session.scalar(
            select(EntityRow).where(EntityRow.id == str(entity_id)).with_for_update()
        )
        if row is None:
            raise KeyError(entity_id)
        entity = Entity.model_validate(row.payload)
        if (
            entity.kind != "person"
            or entity.owner_id != self.owner
            or not entity.enrolled
            or not entity.biometric_consent
            or entity.retention.expires_at is None
            or entity.retention.expires_at != aware(consent.expires_at)
        ):
            raise PermissionError("consent-bound owner person required")
        return row

    def check_person(self, entity_id: UUID, name: str) -> None:
        with Session(self.repo.engine) as session, session.begin():
            row = self.owner_entity(session, entity_id)
            if row.name != name:
                raise PermissionError("current person name confirmation required")

    def reference_count(self, session: Session, entity: Entity) -> int:
        return int(
            session.scalar(
                select(func.count())
                .select_from(FaceReferenceRow)
                .where(
                    FaceReferenceRow.entity_id == str(entity.id),
                    FaceReferenceRow.payload["state"].as_string() == "active",
                )
            )
            or 0
        )

    def attach(self, entity_row: EntityRow, entity: Entity, reference_id: UUID) -> None:
        # Dedicated table is the reverse association, never generic object-reference IDs.
        pass

    def payload_fields(self, session: Session, entity_row: EntityRow) -> dict[str, Any]:
        consent = session.scalar(select(ConsentRow).where(ConsentRow.entity_id == entity_row.id))
        assert consent is not None  # owner_entity locked and validated it in this transaction.
        return {"consent_id": consent.id, "asset_kind": "consented-face-reference"}

    def validate_reference(self, session: Session, row: ReferenceRow) -> None:
        consent = session.scalar(select(ConsentRow).where(ConsentRow.entity_id == row.entity_id))
        if consent is None or row.payload.get("consent_id") != consent.id:
            raise PermissionError("face reference consent binding mismatch")

    def mark_deleted(self, entity_row: EntityRow | None, row: ReferenceRow) -> None:
        row.payload = {**row.payload, "state": "pending-deletion"}

    def cleanup_entity(self, session: Session, row: ReferenceRow) -> EntityRow | None:
        return None  # No generic entity links; avoids reference→consent/entity lock inversion.

    def retire(self, reference_id: UUID, confirmed_name: str, *, confirmed: bool) -> None:
        with self.lock, Session(self.repo.engine) as session, session.begin():
            observed = session.get(FaceReferenceRow, str(reference_id))
            if observed is None or observed.payload["owner_id"] != str(self.owner):
                raise KeyError(reference_id)
            entity = self.owner_entity(session, UUID(observed.entity_id), allow_expired=True)
            if entity.name != confirmed_name:
                raise PermissionError("current person name confirmation required")
            row = session.scalar(
                select(FaceReferenceRow)
                .where(FaceReferenceRow.id == str(reference_id))
                .with_for_update()
            )
            if row is None:
                raise KeyError(reference_id)
            self.audit(
                session, "reference_delete", reference_id, UUID(row.entity_id), confirmed=confirmed
            )
            self.mark_deleted(None, row)
