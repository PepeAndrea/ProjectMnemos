import pytest
from mnemos.tracking import SessionTracker
from mnemos.vision import Box, Detection


def detection(sequence, x=0, source="safe"):
    return Detection("object", 0.9, Box(x, 0, 20, 20), source, sequence)


def test_enter_update_exit_reentry_does_not_claim_identity():
    tracker = SessionTracker(max_missed=0)
    enter = tracker.update([detection(0)], "safe", 0)[0]
    update = tracker.update([detection(1, 1)], "safe", 1)[0]
    exit = tracker.update([], "safe", 2)[0]
    again = tracker.update([detection(3)], "safe", 3)[0]
    assert [enter.kind, update.kind, exit.kind, again.kind] == ["enter", "update", "exit", "enter"]
    assert enter.track_id == update.track_id == exit.track_id
    assert again.track_id != enter.track_id


def test_tracker_bound_and_session_clock():
    tracker = SessionTracker(capacity=2)
    tracker.update([detection(0, x) for x in [0, 100, 200]], "safe", 0)
    assert len(tracker.tracks) == 2 and tracker.dropped == 1
    with pytest.raises(ValueError):
        tracker.update([], "safe", 0)
    with pytest.raises(ValueError):
        tracker.update([], "other", 1)
    tracker.clear()
    assert not tracker.tracks
