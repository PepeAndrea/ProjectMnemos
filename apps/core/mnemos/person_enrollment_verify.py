"""Opt-in synthetic consent HTTP/PostgreSQL verification; no sensor or vector capture."""

import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .biometrics import ConsentRow, TemplateRow
from .runtime import RuntimeLayout
from .storage import EntityRepository, EntityRow, LocalActionRow


def main() -> None:
    layout = RuntimeLayout()
    token = layout.path("data/security/owner-token").read_text().strip()
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}

    def call(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        request = Request(
            "http://127.0.0.1:8000" + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
            method=method,
        )
        with urlopen(request, timeout=10) as response:
            if method == "GET" and path.startswith("/people"):
                assert response.headers["Cache-Control"] == "no-store"
            return json.load(response)

    name = "Synthetic consent verification " + uuid4().hex
    entity_id: str | None = None
    consent_id: str | None = None
    repo = EntityRepository("postgresql+psycopg://mnemos:mnemos@127.0.0.1:5432/mnemos")
    try:
        at = time.monotonic()
        entity = call(
            "POST",
            "/people",
            {
                "name": name,
                "face": True,
                "voice": False,
                "subject_permission_attested": True,
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
        )
        entity_id = entity["id"]
        consent = call("GET", f"/people/{entity_id}/consent")
        consent_id = consent["id"]
        assert consent["face"] is True and consent["voice"] is False
        assert consent["assurance"] == "owner-attested-subject-permission"
        assert any(row["id"] == entity_id for row in call("GET", "/people?limit=1000"))
        renamed = name + " corrected"
        assert call("PUT", f"/people/{entity_id}/name", {"name": renamed})["name"] == renamed
        try:
            call(
                "POST",
                f"/people/{entity_id}/revoke",
                {"confirmed_name": name, "confirm_irreversible": True},
            )
        except HTTPError as error:
            assert error.code == 403
        else:
            raise AssertionError("stale-name revocation accepted")
        assert (
            call(
                "POST",
                f"/people/{entity_id}/revoke",
                {"confirmed_name": renamed, "confirm_irreversible": True},
            )["status"]
            == "revoked-and-deleted"
        )
        assert call("GET", f"/people/{entity_id}/consent")["status"] == "revoked"
        with Session(repo.engine) as session:
            assert session.get(EntityRow, entity_id) is None
            assert (
                session.scalar(select(TemplateRow).where(TemplateRow.consent_id == consent_id))
                is None
            )
            audits = [
                row
                for row in session.scalars(select(LocalActionRow))
                if row.payload.get("result", {})
                .get("proposal", {})
                .get("params", {})
                .get("entity_id")
                == entity_id
            ]
            assert len(audits) == 3
            assert all(name not in json.dumps(row.payload) for row in audits)
        report = {
            "passed": True,
            "scope": "synthetic metadata, real loopback HTTP/PostgreSQL; no biometric samples",
            "flow_ms": (time.monotonic() - at) * 1000,
            "atomic_execution_audits": 3,
            "stale_name_rejected": True,
            "revoked_identity_absent": True,
        }
    finally:
        try:
            if entity_id is not None:
                with Session(repo.engine) as session, session.begin():
                    for row in session.scalars(select(LocalActionRow)):
                        if (
                            row.payload.get("result", {})
                            .get("proposal", {})
                            .get("params", {})
                            .get("entity_id")
                            == entity_id
                        ):
                            session.delete(row)
                    if consent_id is not None:
                        session.execute(
                            delete(TemplateRow).where(TemplateRow.consent_id == consent_id)
                        )
                    session.execute(delete(ConsentRow).where(ConsentRow.entity_id == entity_id))
                    session.execute(delete(EntityRow).where(EntityRow.id == entity_id))
        finally:
            repo.close()
    layout.path("exports/person-enrollment-http.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
