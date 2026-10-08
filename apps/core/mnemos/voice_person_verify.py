"""Opt-in actual Whisper → reviewed synthetic person → consent/revoke on idle dev core."""

import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.request import Request, urlopen
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .biometrics import ConsentRow
from .runtime import RuntimeLayout
from .storage import EntityRepository, EntityRow, LocalActionRow


def main() -> None:
    layout = RuntimeLayout()
    token = layout.path("data/security/owner-token").read_text().strip()
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}

    def call(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        request = Request(
            "http://127.0.0.1:8000" + path,
            method=method,
            headers=headers,
            data=json.dumps(body).encode() if body is not None else None,
        )
        with urlopen(request, timeout=10) as response:
            return json.load(response)

    current = call("GET", "/capture/status")
    if current["state"] in {"starting", "running"}:
        raise RuntimeError("idle development core required; existing capture left untouched")
    repo = EntityRepository("postgresql+psycopg://mnemos:mnemos@127.0.0.1:5432/mnemos")
    name = "Synthetic voice person verification " + uuid4().hex
    capture_id: str | None = None
    entity_id: str | None = None
    approved = False
    try:
        start = time.perf_counter()
        capture_id = call(
            "POST",
            "/capture/start",
            {
                "mode": "speech-replay",
                "camera": False,
                "microphone": True,
                "transcribe": True,
                "language": "en",
            },
        )["id"]
        deadline = time.monotonic() + 15
        while True:
            current = call("GET", "/capture/status")
            if current["id"] != capture_id:
                raise RuntimeError("capture changed during synthetic verification")
            if current["enrollment_proposals"]:
                break
            if (
                current["state"] in {"completed", "failed", "stopped"}
                or time.monotonic() > deadline
            ):
                raise RuntimeError("actual ASR did not produce a reviewable command")
            time.sleep(0.05)
        proposal = current["enrollment_proposals"][0]
        assert proposal["policy"]["allowed"] is False
        proposal_ms = (time.perf_counter() - start) * 1000
        entity_id = str(
            uuid5(NAMESPACE_URL, capture_id + "/" + proposal["utterance_id"] + "/entity")
        )
        start = time.perf_counter()
        person = call(
            "POST",
            f"/capture/{capture_id}/enrollment/{proposal['id']}/approve-person",
            {
                "name": name,
                "face": True,
                "voice": False,
                "subject_permission_attested": True,
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                "confirm_person_enrollment": True,
            },
        )
        reviewed_ms = (time.perf_counter() - start) * 1000
        assert person["id"] == entity_id and person["kind"] == "person" and person["name"] == name
        approved = True
        consent = call("GET", f"/people/{entity_id}/consent")
        assert consent["face"] is True and consent["voice"] is False
        assert consent["assurance"] == "owner-attested-subject-permission"
        with Session(repo.engine) as session:
            audits = [
                row
                for row in session.scalars(select(LocalActionRow))
                if row.payload.get("result", {})
                .get("proposal", {})
                .get("params", {})
                .get("entity_id")
                == entity_id
            ]
            assert (
                len(audits) == 1
                and audits[0].payload["result"]["proposal"]["params"]["reviewed_proposal_id"]
                == proposal["id"]
            )
            assert name not in str(audits[0].payload)
        call("POST", "/capture/stop")
        stopped = call("GET", "/capture/status")
        assert stopped["enrollment_proposals"] == stopped["transcripts"] == []
        call(
            "POST",
            f"/people/{entity_id}/revoke",
            {"confirmed_name": name, "confirm_irreversible": True},
        )
        assert call("GET", f"/people/{entity_id}/consent")["status"] == "revoked"
        report = {
            "passed": True,
            "scope": "actual local Whisper, real HTTP/PostgreSQL, synthetic corrected person metadata; no biometric samples or native sensors",
            "proposal_ms": proposal_ms,
            "owner_person_review_ms": reviewed_ms,
            "anonymous_policy_allowed": False,
            "linked_consent_audits": 1,
            "scope_face_only": True,
            "stop_cleared_private_state": True,
            "revoked": True,
        }
    finally:
        try:
            if capture_id is not None and call("GET", "/capture/status").get("id") == capture_id:
                call("POST", "/capture/stop")
        finally:
            try:
                if entity_id is not None:
                    with Session(repo.engine) as session, session.begin():
                        row = session.get(EntityRow, entity_id)
                        own_fixture = approved or (row is not None and row.name == name)
                        if own_fixture:
                            for audit in session.scalars(select(LocalActionRow)):
                                if (
                                    audit.payload.get("result", {})
                                    .get("proposal", {})
                                    .get("params", {})
                                    .get("entity_id")
                                    == entity_id
                                ):
                                    session.delete(audit)
                            session.execute(
                                delete(ConsentRow).where(ConsentRow.entity_id == entity_id)
                            )
                            session.execute(delete(EntityRow).where(EntityRow.id == entity_id))
            finally:
                repo.close()
    layout.path("exports/voice-person-http.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
