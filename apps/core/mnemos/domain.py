"""Versioned domain contracts. Biometric templates never belong in public entities."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

Score = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Nonempty = Annotated[str, Field(min_length=1, max_length=4096)]


def now() -> datetime:
    return datetime.now(UTC)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    schema_version: Literal[1] = 1


class Provenance(Contract):
    source_id: Nonempty
    observed_at: datetime = Field(default_factory=now)
    method: Nonempty
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def aware_time(self) -> "Provenance":
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at requires a timezone")
        return self


class Retention(Contract):
    scope: Literal["session", "persistent"] = "session"
    expires_at: datetime | None = None
    purpose: Nonempty

    @model_validator(mode="after")
    def aware_expiry(self) -> "Retention":
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError("retention expiry requires a timezone")
        return self


class Entity(Contract):
    id: UUID = Field(default_factory=uuid4)
    kind: Literal[
        "person",
        "object",
        "place",
        "device",
        "concept",
        "vehicle",
        "document",
        "product",
        "machine",
        "component",
        "animal",
    ]
    name: Nonempty
    aliases: list[Nonempty] = Field(default_factory=list, max_length=100)
    attributes: dict[str, str] = Field(default_factory=dict)
    relations: dict[str, list[UUID]] = Field(default_factory=dict)
    reference_ids: list[UUID] = Field(default_factory=list)
    embedding_refs: list[UUID] = Field(default_factory=list)
    provenance: Provenance
    retention: Retention
    confidence: Score
    enrolled: bool = False
    biometric_consent: bool = False
    owner_id: UUID | None = None

    @model_validator(mode="after")
    def identity_boundary(self) -> "Entity":
        if (
            self.kind == "person"
            and self.retention.scope == "persistent"
            and (not self.enrolled or not self.biometric_consent)
        ):
            raise ValueError("persistent person identity requires enrollment and consent")
        if self.biometric_consent and self.kind != "person":
            raise ValueError("biometric consent applies only to people")
        return self


class IdentityEntity(Entity):
    kind: Literal["person"] = "person"
    # Opaque refs to the isolated encrypted biometric store, never template bytes.
    face_template_ids: list[UUID] = Field(default_factory=list)
    voice_template_ids: list[UUID] = Field(default_factory=list)
    authorized_image_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def templates_authorized(self) -> "IdentityEntity":
        if (
            self.face_template_ids or self.voice_template_ids or self.authorized_image_ids
        ) and not (self.enrolled and self.biometric_consent):
            raise ValueError("biometric references require consent and enrollment")
        return self


class Evidence(Contract):
    id: UUID = Field(default_factory=uuid4)
    kind: Literal["detector", "embedding", "local_features", "ocr", "track", "human"]
    score: Score
    provenance: Provenance
    reference: str | None = None


class Observation(Contract):
    id: UUID = Field(default_factory=uuid4)
    modality: Literal["video", "audio", "text", "context"]
    entity_id: UUID | None = None
    candidate_ids: list[UUID] = Field(default_factory=list)
    track_id: str | None = None
    session_id: UUID
    confidence: Score
    context: dict[str, str] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)
    provenance: Provenance
    # This is a volatile reference, never a durable media path.
    buffer_ref: str | None = None


class Event(Contract):
    id: UUID = Field(default_factory=uuid4)
    kind: Literal["enter", "update", "exit", "speech", "commitment", "change"]
    observation_ids: list[UUID] = Field(min_length=1)
    entity_ids: list[UUID] = Field(default_factory=list)
    confidence: Score
    provenance: Provenance


class Utterance(Contract):
    id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID
    speaker_session_id: Nonempty
    speaker_entity_id: UUID | None = None
    speaker_confidence: Score = 0
    text: Nonempty
    language: Literal["it", "en"]
    start_seconds: float = Field(ge=0, allow_inf_nan=False)
    end_seconds: float = Field(ge=0, allow_inf_nan=False)
    final: bool = False
    confidence: Score
    source_audio_id: UUID | None = None
    provenance: Provenance

    @model_validator(mode="after")
    def ordered(self) -> "Utterance":
        if self.end_seconds < self.start_seconds:
            raise ValueError("negative utterance duration")
        if not self.final and self.source_audio_id is not None:
            raise ValueError("partial transcript cannot reference persistent audio")
        return self


class Conversation(Contract):
    id: UUID = Field(default_factory=uuid4)
    started_at: datetime = Field(default_factory=now)
    ended_at: datetime | None = None
    participant_ids: list[UUID] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    utterance_ids: list[UUID] = Field(default_factory=list)
    summary: str | None = None
    decision_ids: list[UUID] = Field(default_factory=list)
    task_ids: list[UUID] = Field(default_factory=list)
    commitment_ids: list[UUID] = Field(default_factory=list)
    linked_entity_ids: list[UUID] = Field(default_factory=list)
    recording_enabled: bool = False
    transcript_persistence_enabled: bool = False
    provenance: Provenance


class Memory(Contract):
    id: UUID = Field(default_factory=uuid4)
    kind: Literal["semantic", "episodic", "prospective"]
    text: Nonempty
    entity_ids: list[UUID] = Field(default_factory=list)
    confidence: Score
    importance: Score
    provenance: Provenance
    retention: Retention
    supersedes: UUID | None = None


class Task(Contract):
    id: UUID = Field(default_factory=uuid4)
    text: Nonempty
    state: Literal["open", "done", "cancelled"] = "open"
    due_at: datetime | None = None
    provenance: Provenance


class Trigger(Contract):
    due_at: datetime | None = None
    entity_visible: UUID | None = None
    place: str | None = None
    topic: str | None = None

    @model_validator(mode="after")
    def nonempty(self) -> "Trigger":
        if not any([self.due_at, self.entity_visible, self.place, self.topic]):
            raise ValueError("trigger needs at least one condition")
        if self.due_at is not None and self.due_at.tzinfo is None:
            raise ValueError("due_at requires timezone")
        return self


class Reminder(Contract):
    id: UUID = Field(default_factory=uuid4)
    text: Nonempty
    trigger: Trigger
    state: Literal["pending", "notified", "done", "snoozed", "ignored"] = "pending"
    snooze_until: datetime | None = None
    urgency: Score = 0.5
    provenance: Provenance


class Risk(StrEnum):
    AUTOMATIC = "automatic"
    AUDIT = "audit"
    CONFIRMATION = "confirmation"
    STRONG = "strong-confirmation"
    PROHIBITED = "prohibited"


class ActionProposal(Contract):
    id: UUID = Field(default_factory=uuid4)
    kind: Literal[
        "consent_expire",
        "person_enroll",
        "person_revoke",
        "biometric_store",
        "biometric_read",
        "track_bind",
        "reference_store",
        "reference_read",
        "reference_delete",
        "reference_expire",
        "entity_create",
        "entity_update",
        "memory",
        "task",
        "reminder",
        "notify",
        "draft_email",
        "calendar",
        "crm",
        "delete",
        "payment",
        "sensor_start",
        "sensor_stop",
    ]
    params: dict[str, Any]
    source_event_id: UUID
    requested_by: UUID | None = None
    confidence: Score
    # Claimed risk is advisory; policy computes actual risk independently.
    risk: Risk
    provenance: Provenance


class ActionPolicyDecision(Contract):
    proposal_id: UUID
    allowed: bool
    risk: Risk
    reason: Nonempty
    confirmation_required: bool


class ActionExecution(Contract):
    proposal_id: UUID
    status: Literal["succeeded", "denied", "failed"]
    result: dict[str, Any] = Field(default_factory=dict)
    policy: ActionPolicyDecision
    executed_at: datetime = Field(default_factory=now)
