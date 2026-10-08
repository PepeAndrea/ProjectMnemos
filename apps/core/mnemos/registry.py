"""Owner-authenticated manual enrollment with atomic policy execution audit.

Speech and biometric enrollment require dedicated verified flows; a caller-supplied
transcript, speaker score or consent boolean cannot grant authority here.
"""

from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain import ActionExecution, ActionProposal, Entity, Provenance, Risk
from .policy import Authorization, PolicyEngine
from .storage import EntityRepository, EntityRow, LocalActionRow


class GovernedRegistry:
    def __init__(self, repository: EntityRepository, owner_id: UUID):
        self.repository, self.owner_id = repository, owner_id

    def save(
        self, entity: Entity, *, create: bool = True, reviewed_proposal_id: UUID | None = None
    ) -> Entity:
        if entity.kind == "person":
            raise PermissionError("dedicated verified person enrollment required")
        if entity.retention.scope != "persistent":
            raise ValueError("session entities must remain in hot memory")
        if entity.owner_id not in (None, self.owner_id):
            raise PermissionError("entity belongs to another owner")
        operation: Literal["entity_create", "entity_update"] = (
            "entity_create" if create else "entity_update"
        )
        provenance = Provenance(
            source_id="owner-voice-review" if reviewed_proposal_id else "owner-dashboard",
            method="human",
        )
        proposal = ActionProposal(
            kind=operation,
            params={"entity_id": str(entity.id)},
            source_event_id=uuid4(),
            requested_by=self.owner_id,
            confidence=1,
            risk=Risk.AUDIT,
            provenance=provenance,
        )
        decision = PolicyEngine().evaluate(proposal, Authorization(self.owner_id, True))
        if not decision.allowed:
            raise PermissionError(decision.reason)
        value = Entity.model_validate(
            {
                **entity.model_dump(),
                "owner_id": self.owner_id,
                "provenance": provenance.model_dump(),
            }
        )
        with Session(self.repository.engine) as session, session.begin():
            row = session.scalar(
                select(EntityRow).where(EntityRow.id == str(value.id)).with_for_update()
            )
            if create and row is not None:
                raise ValueError("entity already exists")
            if not create and row is None:
                raise KeyError(value.id)
            if row is None:
                if value.reference_ids or value.embedding_refs or value.relations:
                    raise PermissionError("references require verified evidence acquisition")
                row = EntityRow(id=str(value.id))
                session.add(row)
            else:
                previous = Entity.model_validate(row.payload)
                # Generic editing cannot convert an object to an identity, inject model
                # references, reassign ownership or silently expand retention.
                for field in ("kind", "reference_ids", "embedding_refs", "relations", "retention"):
                    if getattr(previous, field) != getattr(value, field):
                        raise PermissionError("protected enrollment fields cannot be changed")
                if previous.owner_id not in (None, self.owner_id):
                    raise PermissionError("entity belongs to another owner")
            row.kind, row.name, row.payload = value.kind, value.name, value.model_dump(mode="json")
            execution = ActionExecution(
                proposal_id=proposal.id,
                status="succeeded",
                policy=decision,
                result={
                    "proposal": proposal.model_dump(mode="json"),
                    "entity_id": str(value.id),
                    **(
                        {"reviewed_proposal_id": str(reviewed_proposal_id)}
                        if reviewed_proposal_id
                        else {}
                    ),
                },
            )
            session.add(
                LocalActionRow(
                    id=str(proposal.id),
                    created_at=execution.executed_at,
                    payload=execution.model_dump(mode="json"),
                )
            )
        return value

    def delete(self, entity_id: UUID, confirmed_name: str, confirmed: bool) -> ActionExecution:
        """Explicit irreversible owner action; never infer confirmation from speech."""
        proposal = ActionProposal(
            kind="delete",
            params={"entity_id": str(entity_id)},
            source_event_id=uuid4(),
            requested_by=self.owner_id,
            confidence=1,
            risk=Risk.STRONG,
            provenance=Provenance(source_id="owner-dashboard", method="human"),
        )
        decision = PolicyEngine().evaluate(
            proposal, Authorization(self.owner_id, True, strong_confirmation=confirmed)
        )
        if not decision.allowed:
            raise PermissionError(decision.reason)
        with Session(self.repository.engine) as session, session.begin():
            row = session.scalar(
                select(EntityRow).where(EntityRow.id == str(entity_id)).with_for_update()
            )
            if row is None:
                raise KeyError(entity_id)
            value = Entity.model_validate(row.payload)
            if value.owner_id not in (None, self.owner_id):
                raise PermissionError("entity belongs to another owner")
            if value.name != confirmed_name:
                raise PermissionError("confirmation must match the current entity name")
            if value.kind == "person" or value.reference_ids or value.embedding_refs:
                raise PermissionError("dedicated reference and biometric revocation required")
            # Generic enrollment cannot add relations, so concurrent requests cannot
            # create new inbound links while this deletion checks legacy records.
            for other in session.scalars(select(EntityRow)).yield_per(100):
                if other.id == row.id:
                    continue
                related = Entity.model_validate(other.payload)
                if any(entity_id in targets for targets in related.relations.values()):
                    raise PermissionError("entity has dependent relations")
            execution = ActionExecution(
                proposal_id=proposal.id,
                status="succeeded",
                policy=decision,
                result={"proposal": proposal.model_dump(mode="json"), "entity_id": str(entity_id)},
            )
            session.delete(row)
            session.add(
                LocalActionRow(
                    id=str(proposal.id),
                    created_at=execution.executed_at,
                    payload=execution.model_dump(mode="json"),
                )
            )
        return execution
