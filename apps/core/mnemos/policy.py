"""Fail-closed action policy. Model-supplied risk cannot grant authority."""

from dataclasses import dataclass
from typing import ClassVar
from uuid import UUID

from .domain import ActionPolicyDecision, ActionProposal, Risk


@dataclass(frozen=True)
class Authorization:
    owner_id: UUID
    authenticated_owner: bool
    speaker_id: UUID | None = None
    speaker_confidence: float = 0
    confirmation: bool = False
    strong_confirmation: bool = False


class PolicyEngine:
    risks: ClassVar[dict[str, Risk]] = {
        "consent_expire": Risk.AUTOMATIC,
        "person_enroll": Risk.CONFIRMATION,
        "person_revoke": Risk.STRONG,
        "biometric_store": Risk.CONFIRMATION,
        "biometric_read": Risk.AUDIT,
        "track_bind": Risk.CONFIRMATION,
        "reference_store": Risk.CONFIRMATION,
        "reference_read": Risk.AUDIT,
        "reference_delete": Risk.STRONG,
        "reference_expire": Risk.AUTOMATIC,
        "entity_create": Risk.AUDIT,
        "entity_update": Risk.AUDIT,
        "memory": Risk.AUDIT,
        "task": Risk.AUDIT,
        "reminder": Risk.AUDIT,
        "notify": Risk.AUTOMATIC,
        "draft_email": Risk.AUDIT,
        "calendar": Risk.CONFIRMATION,
        "crm": Risk.CONFIRMATION,
        "delete": Risk.STRONG,
        "payment": Risk.PROHIBITED,
        "sensor_start": Risk.CONFIRMATION,
        "sensor_stop": Risk.AUTOMATIC,
    }

    def evaluate(self, proposal: ActionProposal, auth: Authorization) -> ActionPolicyDecision:
        risk = self.risks[proposal.kind]
        owner = auth.authenticated_owner or (
            auth.speaker_id == auth.owner_id and auth.speaker_confidence >= 0.95
        )
        required = risk in {Risk.CONFIRMATION, Risk.STRONG}
        reason = "authorized"
        if not owner or proposal.requested_by != auth.owner_id:
            reason = "owner authorization required"
        elif proposal.confidence < 0.8:
            reason = "insufficient command confidence"
        elif risk == Risk.PROHIBITED:
            reason = "out of scope"
        elif risk == Risk.STRONG and not auth.strong_confirmation:
            reason = "strong confirmation required"
        elif risk == Risk.CONFIRMATION and not auth.confirmation:
            reason = "confirmation required"
        return ActionPolicyDecision(
            proposal_id=proposal.id,
            allowed=reason == "authorized",
            risk=risk,
            reason=reason,
            confirmation_required=required,
        )
