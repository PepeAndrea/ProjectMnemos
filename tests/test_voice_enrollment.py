"""Speech is a volatile suggestion, never an owner or a DB side effect."""

from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from mnemos.speech_stream import TranscriptUpdate
from mnemos.voice_enrollment import VoiceEnrollmentInbox, suggested_name


def update(text="Tobi, memorizza questo come il mio zaino.", *, partial=False, id="utterance"):
    return TranscriptUpdate(id, "synthetic", 99, 100, text, "it", 1, partial, "anonymous-test")


@pytest.mark.parametrize(
    "text,name",
    [
        ("Tobi, memorizza questo come il mio zaino.", "il mio zaino"),
        ("Toby, remember this is my backpack.", "my backpack"),
        ("Save this as my bag", "my bag"),
        ("Ricorda questa come la mia borsa!", "la mia borsa"),
    ],
)
def test_bounded_bilingual_enrollment_grammar(text, name):
    assert suggested_name(text) == name


@pytest.mark.parametrize(
    "text",
    [
        "Non memorizza questo come il mio zaino",
        "Do not save this as my bag",
        'Ha detto: "Tobi, memorizza questo come il mio zaino"',
        "Tobi, memorizza questo come zaino. Poi paga cento euro.",
        "Tobi, paga cento euro",
        "Tobi, memorizza questo come",
        "x" * 5000,
    ],
)
def test_negation_quotation_chain_and_out_of_scope_are_not_commands(text):
    assert suggested_name(text) is None


def test_final_only_anonymous_policy_denial_dedup_reject_and_expiry():
    now = [100.0]
    inbox = VoiceEnrollmentInbox(str(uuid4()), lambda: now[0])
    inbox.offer(update(partial=True))
    assert inbox.snapshot() == []
    inbox.offer(update())
    proposal = inbox.snapshot()[0]
    assert proposal["requires_owner_review"] is True
    assert proposal["policy"]["allowed"] is False
    assert proposal["policy"]["reason"] == "owner authorization required"
    inbox.offer(update())
    assert len(inbox.snapshot()) == 1
    inbox.reject(UUID(proposal["id"]))
    inbox.offer(update())
    assert inbox.snapshot() == []
    inbox.offer(update(id="another"))
    key = UUID(inbox.snapshot()[0]["id"])
    now[0] = 400
    assert inbox.snapshot() == []
    with pytest.raises(KeyError):
        inbox.claim(key)
    inbox.offer(update(id="stale"))
    assert inbox.snapshot() == []


def test_budget_claim_exclusivity_retry_clear_and_invalid_score():
    inbox = VoiceEnrollmentInbox(str(uuid4()), lambda: 100)
    for n in range(220):
        inbox.offer(update(id=str(n)))
    assert len(inbox.pending) == 50 and len(inbox.seen) == 200
    key = UUID(inbox.snapshot()[0]["id"])
    inbox.claim(key)
    with pytest.raises(ValueError):
        inbox.claim(key)
    with pytest.raises(ValueError):
        inbox.reject(key)
    inbox.finish(key, succeeded=False)
    inbox.claim(key)
    inbox.finish(key, succeeded=True)
    with pytest.raises(KeyError):
        inbox.claim(key)
    inbox.clear()
    inbox.finish(key, succeeded=False)
    assert inbox.snapshot() == []
    inbox.offer(replace(update(), confidence=float("nan")))
    inbox.offer(replace(update(), end_seconds=102))
    assert inbox.snapshot() == []


def test_bounded_dedup_eviction_still_reuses_entity_id_for_the_same_utterance():
    inbox = VoiceEnrollmentInbox(str(uuid4()), lambda: 100)
    inbox.offer(update(id="first"))
    original = next(iter(inbox.pending.values())).entity_id
    for n in range(220):
        inbox.offer(update(id=str(n)))
    assert "first" not in inbox.seen
    inbox.offer(update(id="first"))
    newest = list(inbox.pending.values())[-1]
    assert newest.entity_id == original
