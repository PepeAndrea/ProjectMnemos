"""Opt-in loopback ASR → anonymous proposal → explicit synthetic owner review.

Requires an already started idle development core and the generated speech fixture.
Never opens a native sensor. Creates/removes only a uniquely named synthetic entity.
"""

import json
import time
from urllib.request import Request, urlopen
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from .runtime import RuntimeLayout
from .storage import EntityRepository, EntityRow, LocalActionRow


def main() -> None:
    layout = RuntimeLayout()
    token = layout.path("data/security/owner-token").read_text().strip()
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}

    def call(method: str, path: str, body: dict[str, object] | None = None) -> dict[str, object]:
        request = Request(
            "http://127.0.0.1:8000" + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
            method=method,
        )
        with urlopen(request, timeout=10) as response:
            value: dict[str, object] = json.load(response)
            return value

    status = call("GET", "/capture/status")
    if status["state"] in {"starting", "running"}:
        raise RuntimeError(
            "verification requires an idle core; existing capture was left untouched"
        )
    name = "Synthetic voice review verification " + uuid4().hex
    capture_id: str | None = None
    repo = EntityRepository("postgresql+psycopg://mnemos:mnemos@127.0.0.1:5432/mnemos")
    try:
        at = time.monotonic()
        started = call(
            "POST",
            "/capture/start",
            {
                "mode": "speech-replay",
                "camera": False,
                "microphone": True,
                "transcribe": True,
                "language": "en",
            },
        )
        capture_id = str(started["id"])
        deadline = time.monotonic() + 15
        proposals: list[dict[str, object]] = []
        while time.monotonic() < deadline:
            current = call("GET", "/capture/status")
            if current["id"] != capture_id:
                raise RuntimeError("capture changed during synthetic verification")
            proposals = current["enrollment_proposals"]  # type: ignore[assignment]
            if proposals:
                break
            if current["state"] in {"completed", "failed", "stopped"}:
                break
            time.sleep(0.05)
        assert proposals, "actual ASR did not produce a reviewable command"
        proposal = proposals[0]
        policy = proposal["policy"]
        assert isinstance(policy, dict) and policy["allowed"] is False
        proposed_ms = (time.monotonic() - at) * 1000
        before = time.monotonic()
        entity = call(
            "POST",
            f"/capture/{capture_id}/enrollment/{proposal['id']}/approve",
            {
                "name": name,
                "confirm_catalog_enrollment": True,
            },
        )
        review_ms = (time.monotonic() - before) * 1000
        assert entity["name"] == name
        with Session(repo.engine) as session:
            rows = list(session.scalars(select(LocalActionRow)))
            audits = [
                row
                for row in rows
                if row.payload.get("result", {}).get("entity_id") == entity["id"]
            ]
            assert len(audits) == 1
            assert audits[0].payload["result"]["reviewed_proposal_id"] == proposal["id"]
        call("POST", "/capture/stop")
        stopped = call("GET", "/capture/status")
        assert stopped["enrollment_proposals"] == stopped["transcripts"] == []
        report = {
            "passed": True,
            "scope": "synthetic speech, real Whisper/HTTP/PostgreSQL; no native sensors",
            "proposal_ms": proposed_ms,
            "explicit_review_ms": review_ms,
            "anonymous_policy_allowed": False,
            "linked_execution_audits": 1,
            "stop_cleared_private_state": True,
        }
    finally:
        try:
            if capture_id is not None:
                current = call("GET", "/capture/status")
                if current.get("id") == capture_id:
                    call("POST", "/capture/stop")
        finally:
            # Only this run's unique synthetic entity and its test audit.
            try:
                with Session(repo.engine) as session, session.begin():
                    entities = list(
                        session.scalars(select(EntityRow).where(EntityRow.name == name))
                    )
                    ids = {entity_row.id for entity_row in entities}
                    for audit_row in session.scalars(select(LocalActionRow)):
                        if audit_row.payload.get("result", {}).get("entity_id") in ids:
                            session.delete(audit_row)
                    for entity_row in entities:
                        session.delete(entity_row)
            finally:
                repo.close()
    layout.path("exports/voice-enrollment-http.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
