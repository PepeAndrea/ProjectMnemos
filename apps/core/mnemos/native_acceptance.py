"""Explicit local native acceptance; dry-run by default, no media exported."""

import argparse
import json
import math
import time
from collections.abc import Callable
from typing import Any
from urllib.request import Request, urlopen

from .media import MediaFailureCode
from .runtime import RuntimeLayout


def request_plan(camera: bool, microphone: bool, duration: float) -> dict[str, Any]:
    if not camera and not microphone or not math.isfinite(duration) or not 3 <= duration <= 30:
        raise ValueError("select a sensor and a duration from 3 to 30 seconds")
    return {
        "mode": "native",
        "camera": camera,
        "microphone": microphone,
        "camera_consent": camera,
        "microphone_consent": microphone,
        "transcribe": False,
        "language": "it",
    }


def verify_native(
    call: Callable[[str, str, dict[str, Any] | None], Any],
    camera: bool,
    microphone: bool,
    duration: float,
    *,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    body = request_plan(camera, microphone, duration)
    previous = call("GET", "/capture/status", None)
    if previous.get("worker_active") or previous["state"] in {"running", "starting"}:
        raise RuntimeError("an existing sensor session is active; it was not stopped or replaced")
    capture_id = None
    started = clock()
    last: dict[str, Any] = {}
    stopped: dict[str, Any] = {}
    preview_valid = False
    failure: str | None = None
    try:
        status = call("POST", "/capture/start", body)
        capture_id = status.get("id")
        if not capture_id:
            raise RuntimeError("native session identifier missing")
        deadline = clock() + duration
        while clock() < deadline:
            last = call("GET", "/capture/status", None)
            if last.get("id") != capture_id:
                raise RuntimeError("session changed during native verification")
            if last["state"] in {"failed", "completed", "stopped"}:
                break
            if camera and not preview_valid and last.get("processed_frames", 0) > 0:
                jpeg = call("GET", "/capture/frame", None)
                preview_valid = (
                    isinstance(jpeg, bytes)
                    and jpeg.startswith(b"\xff\xd8")
                    and jpeg.endswith(b"\xff\xd9")
                )
                # Retain no image reference across the next iteration or report.
                del jpeg
            sleep(0.2)
    except Exception:  # noqa: BLE001 - do not export HTTP/driver/private response details
        failure = "verification-request-failed"
    finally:
        if capture_id:
            try:
                current = call("GET", "/capture/status", None)
                # Do not stop a replacement session that this verifier did not start.
                if current.get("id") == capture_id:
                    stopped = call("POST", "/capture/stop", None)
                else:
                    failure = "session-changed-before-cleanup"
            except Exception:  # noqa: BLE001 - report bounded cleanup failure only
                failure = "cleanup-request-failed"

    def count(key: str) -> int:
        value = last.get(key, 0)
        return (
            value
            if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < 10**9
            else 0
        )

    known = {code.value for code in MediaFailureCode} | {
        "video-source-failed",
        "audio-source-failed",
        "sensor-cleanup-failed",
    }
    code = last.get("error_code")
    error_code = (
        code if code in known else "unclassified-source-failure" if last.get("error") else None
    )
    cleanup = (
        stopped.get("state") == "stopped"
        and not stopped.get("worker_active")
        and not stopped.get("source_cleanup_failed")
        and stopped.get("audio_buffer_bytes") == stopped.get("video_buffer_bytes") == 0
    )
    camera_observed = bool(camera and count("processed_frames") > 0 and preview_valid)
    microphone_observed = bool(microphone and count("audio_chunks") > 0)
    passed = bool(
        not failure
        and not error_code
        and cleanup
        and (not camera or camera_observed)
        and (not microphone or microphone_observed)
        and last.get("state") == "running"
    )
    return {
        "passed": passed,
        "scope": "explicit local native sensors; counts/preview contract only, not detection/ASR/identity calibration",
        "requested_camera": camera,
        "requested_microphone": microphone,
        "elapsed_seconds": round(clock() - started, 3),
        "requested_seconds": duration,
        "camera_frames_observed": camera_observed,
        "microphone_chunks_observed": microphone_observed,
        "video_frames": count("video_frames"),
        "processed_frames": count("processed_frames"),
        "audio_chunks": count("audio_chunks"),
        "error_code": error_code,
        "verification_error": failure,
        "cleanup_verified": cleanup,
        "media_exported": False,
        "transcription_enabled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--camera", action="store_true", help="explicit camera consent when combined with --run"
    )
    parser.add_argument(
        "--microphone",
        action="store_true",
        help="explicit microphone consent when combined with --run",
    )
    parser.add_argument("--duration", type=float, default=5)
    parser.add_argument(
        "--run", action="store_true", help="actually open selected sensors; omit for dry-run"
    )
    args = parser.parse_args()
    plan = request_plan(args.camera, args.microphone, args.duration)
    if not args.run:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "request": plan,
                    "duration_seconds": args.duration,
                    "media_exported": False,
                    "report": "runtime/exports/native-acceptance.json",
                },
                indent=2,
            )
        )
        return
    layout = RuntimeLayout()
    layout.configure()
    token = layout.path("data/security/owner-token").read_text().strip()

    def call(method: str, path: str, body: dict[str, Any] | None) -> Any:
        request = Request(
            "http://127.0.0.1:8000" + path,
            data=json.dumps(body).encode() if body else None,
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            method=method,
        )
        with urlopen(request, timeout=8) as response:
            return response.read() if path == "/capture/frame" else json.load(response)

    report = verify_native(call, args.camera, args.microphone, args.duration)
    layout.path("exports/native-acceptance.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
