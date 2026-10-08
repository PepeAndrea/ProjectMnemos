"""Volatile final-transcript suggestions. Speaker text never grants authority."""

import math
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5

from .domain import ActionProposal, Provenance, Risk
from .policy import Authorization, PolicyEngine
from .speech_stream import TranscriptUpdate

COMMAND = re.compile(
    r"^(?:(?:tobi|toby)\s*[,.:!?-]?\s*)?"
    r"(?:(?:memorizza|ricorda)\s+(?:questo|questa)\s+(?:come|è)|"
    r"(?:remember|save)\s+this\s+(?:as|is))\s+(.+)$",
    re.IGNORECASE,
)


def suggested_name(text: str) -> str | None:
    # Anchored one-clause grammar avoids quotations, negated requests and chained
    # actions. Recognition of the observed ASR spelling 'Toby' is not speaker ID.
    if len(text) > 4096:
        return None
    match = COMMAND.fullmatch(text.strip())
    if match is None:
        return None
    name = match.group(1).strip().rstrip(".!?").strip()
    if not 1 <= len(name) <= 256 or any(char in name for char in ".!?;\n\r"):
        return None
    return name


@dataclass(frozen=True)
class EnrollmentSuggestion:
    proposal: ActionProposal
    entity_id: UUID
    utterance_id: str
    expires_at: float


class VoiceEnrollmentInbox:
    def __init__(self, capture_id: str, clock: Callable[[], float] = time.monotonic):
        self.capture_id, self.clock = capture_id, clock
        self.pending: dict[UUID, EnrollmentSuggestion] = {}
        self.claimed: set[UUID] = set()
        self.seen: dict[str, float] = {}
        self.lock = threading.RLock()

    def expire(self) -> None:
        with self.lock:
            at = self.clock()
            self.pending = {
                key: value for key, value in self.pending.items() if value.expires_at > at
            }
            self.claimed.intersection_update(self.pending)
            self.seen = {key: until for key, until in self.seen.items() if until > at}

    def offer(self, update: TranscriptUpdate) -> None:
        with self.lock:
            self.expire()
            if update.partial or update.id in self.seen:
                return
            at = self.clock()
            if (
                not math.isfinite(update.end_seconds)
                or not at - 300 < update.end_seconds <= at + 1
                or not math.isfinite(update.confidence)
                or not 0 <= update.confidence <= 1
            ):
                return
            self.seen[update.id] = update.end_seconds + 300
            while len(self.seen) > 200:
                del self.seen[next(iter(self.seen))]
            name = suggested_name(update.text)
            if name is None:
                return
            proposal = ActionProposal(
                kind="entity_create",
                params={"suggested_name": name},
                source_event_id=uuid5(NAMESPACE_URL, self.capture_id + "/" + update.id),
                requested_by=None,
                confidence=update.confidence,
                risk=Risk.AUDIT,
                provenance=Provenance(source_id="anonymous-local-asr", method="speech-proposal"),
            )
            self.pending[proposal.id] = EnrollmentSuggestion(
                proposal,
                uuid5(NAMESPACE_URL, self.capture_id + "/" + update.id + "/entity"),
                update.id,
                update.end_seconds + 300,
            )
            while len(self.pending) > 50:
                key = next(iter(self.pending))
                del self.pending[key]
                self.claimed.discard(key)

    def snapshot(self) -> list[dict[str, object]]:
        with self.lock:
            self.expire()
            values = []
            for key, item in self.pending.items():
                # The anonymous proposal fails policy even at perfect ASR confidence.
                decision = PolicyEngine().evaluate(item.proposal, Authorization(UUID(int=0), False))
                values.append(
                    {
                        "id": str(key),
                        "utterance_id": item.utterance_id,
                        "suggested_name": item.proposal.params["suggested_name"],
                        "confidence": item.proposal.confidence,
                        "requires_owner_review": True,
                        "state": "committing" if key in self.claimed else "pending",
                        "policy": decision.model_dump(mode="json"),
                    }
                )
            return values

    def claim(self, proposal_id: UUID) -> EnrollmentSuggestion:
        with self.lock:
            self.expire()
            item = self.pending.get(proposal_id)
            if item is None:
                raise KeyError(proposal_id)
            if proposal_id in self.claimed:
                raise ValueError("proposal approval already in progress")
            self.claimed.add(proposal_id)
            return item

    def finish(self, proposal_id: UUID, *, succeeded: bool) -> None:
        with self.lock:
            self.claimed.discard(proposal_id)
            if succeeded:
                self.pending.pop(proposal_id, None)
            self.expire()

    def reject(self, proposal_id: UUID) -> None:
        with self.lock:
            self.expire()
            if proposal_id in self.claimed:
                raise ValueError("proposal approval already in progress")
            if self.pending.pop(proposal_id, None) is None:
                raise KeyError(proposal_id)

    def clear(self) -> None:
        with self.lock:
            self.pending.clear()
            self.claimed.clear()
            self.seen.clear()
