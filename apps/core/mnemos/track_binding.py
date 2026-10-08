"""Audited human association to an existing object; no media or recognition claim."""

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain import ActionExecution, ActionProposal, Entity, Provenance, Risk
from .policy import Authorization, PolicyEngine
from .storage import EntityRepository, EntityRow, LocalActionRow


def authorize_binding(
    repo: EntityRepository,
    owner_id: UUID,
    capture_id: UUID,
    track_id: UUID,
    entity_id: UUID,
    *,
    confirmed: bool,
) -> None:
    proposal = ActionProposal(
        kind="track_bind",
        requested_by=owner_id,
        confidence=1,
        risk=Risk.CONFIRMATION,
        source_event_id=uuid4(),
        params={
            "capture_id": str(capture_id),
            "track_id": str(track_id),
            "entity_id": str(entity_id),
        },
        provenance=Provenance(source_id="owner-observed-track-review", method="human"),
    )
    decision = PolicyEngine().evaluate(
        proposal, Authorization(owner_id, True, confirmation=confirmed)
    )
    if not decision.allowed:
        raise PermissionError(decision.reason)
    with Session(repo.engine) as session, session.begin():
        row = session.scalar(
            select(EntityRow).where(EntityRow.id == str(entity_id)).with_for_update()
        )
        if row is None:
            raise KeyError(entity_id)
        entity = Entity.model_validate(row.payload)
        if entity.kind != "object" or entity.owner_id != owner_id or not entity.enrolled:
            raise PermissionError("enrolled owner object required; people use dedicated enrollment")
        execution = ActionExecution(
            proposal_id=proposal.id,
            status="succeeded",
            policy=decision,
            result={"proposal": proposal.model_dump(mode="json"), "scope": "human-session-track"},
        )
        session.add(
            LocalActionRow(
                id=str(proposal.id),
                created_at=execution.executed_at,
                payload=execution.model_dump(mode="json"),
            )
        )
