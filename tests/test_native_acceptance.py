import json

import pytest
from mnemos.native_acceptance import request_plan, verify_native


def test_native_plan_explicit_scopes_and_bounds():
    assert request_plan(True, False, 5)["camera_consent"]
    assert not request_plan(True, False, 5)["microphone_consent"]
    assert not request_plan(False, True, 5)["transcribe"]
    for args in (
        (False, False, 5),
        (True, False, 0),
        (True, False, 31),
        (True, False, float("nan")),
    ):
        with pytest.raises(ValueError):
            request_plan(*args)


def scenario(
    *, prior=False, fault=False, replacement=False, cleanup_error=False, request_error=False
):
    calls = []
    started = False
    ticks = [0.0]

    def call(method, path, body):
        nonlocal started
        calls.append((method, path, body))
        if path == "/capture/start":
            started = True
            return {"id": "own-session"}
        if path == "/capture/frame":
            return b"\xff\xd8private-test-pixels\xff\xd9"
        if path == "/capture/stop":
            return {
                "state": "stopped",
                "worker_active": False,
                "source_cleanup_failed": cleanup_error,
                "audio_buffer_bytes": 0,
                "video_buffer_bytes": 0,
            }
        if not started:
            return {"state": "running" if prior else "idle", "worker_active": prior}
        if request_error:
            raise RuntimeError("private-driver/path/token")
        return {
            "id": "replacement" if replacement else "own-session",
            "state": "failed" if fault else "running",
            "error": "private-driver/path/token" if fault else None,
            "error_code": "camera-open-failed" if fault else None,
            "processed_frames": 3,
            "video_frames": 4,
            "audio_chunks": 100,
            "transcripts": [{"text": "private speech"}],
            "tracks": [{"name": "private person"}],
        }

    def sleep(seconds):
        ticks[0] += seconds

    return call, calls, sleep, lambda: ticks[0]


def test_native_verify_aggregate_only_and_stops_owned_session():
    call, calls, sleep, clock = scenario()
    report = verify_native(call, True, True, 3, sleep=sleep, clock=clock)
    assert report["passed"] and report["cleanup_verified"]
    assert report["camera_frames_observed"] and report["microphone_chunks_observed"]
    assert not report["media_exported"] and "private" not in json.dumps(report)
    assert calls[-1][:2] == ("POST", "/capture/stop")
    assert next(c for c in calls if c[1] == "/capture/start")[2]["camera_consent"]


def test_native_verify_never_interrupts_preexisting_or_replacement_session():
    call, calls, sleep, clock = scenario(prior=True)
    with pytest.raises(RuntimeError, match="existing"):
        verify_native(call, True, False, 3, sleep=sleep, clock=clock)
    assert not any(c[0] == "POST" for c in calls)
    call, calls, sleep, clock = scenario(replacement=True)
    result = verify_native(call, True, False, 3, sleep=sleep, clock=clock)
    assert not result["passed"] and not any(c[1] == "/capture/stop" for c in calls)


@pytest.mark.parametrize(
    "flags", [{"fault": True}, {"cleanup_error": True}, {"request_error": True}]
)
def test_native_verify_failure_reports_sanitized_and_not_passed(flags):
    call, _calls, sleep, clock = scenario(**flags)
    report = verify_native(call, True, False, 3, sleep=sleep, clock=clock)
    assert not report["passed"] and "private" not in json.dumps(report)
    if flags.get("fault"):
        assert report["error_code"] == "camera-open-failed"
