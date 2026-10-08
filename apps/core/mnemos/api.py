"""Authenticated local REST surface. No device or sensor starts at import time."""

import asyncio
import os
import secrets
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from pydantic import Field, StrictBool
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .biometrics import BiometricKey, PersonEnrollment
from .capture import CaptureSession, build_capture
from .domain import (
    ActionExecution,
    ActionProposal,
    Contract,
    Entity,
    Nonempty,
    Provenance,
    Reminder,
    Retention,
    Risk,
)
from .face_references import FaceReferences
from .policy import Authorization, PolicyEngine
from .references import ObjectReferences
from .registry import GovernedRegistry
from .runtime import RuntimeLayout
from .scheduler import TemporalScheduler
from .storage import EntityRepository
from .track_binding import authorize_binding


class CaptureRequest(Contract):
    mode: Literal["replay", "native", "speech-replay"] = "replay"
    camera: StrictBool = True
    microphone: StrictBool = True
    camera_consent: StrictBool = False
    camera_index: Annotated[int, Field(ge=0, le=4)] | None = None
    microphone_consent: StrictBool = False
    transcribe: StrictBool = False
    language: Literal["auto", "it", "en"] = "it"


class DeleteEntityRequest(Contract):
    confirmed_name: Nonempty
    confirm_irreversible: StrictBool = False


class ApproveVoiceEnrollmentRequest(Contract):
    name: Nonempty
    confirm_catalog_enrollment: StrictBool = False


class RenamePersonRequest(Contract):
    name: Nonempty


class PersonEnrollmentRequest(Contract):
    name: Nonempty
    face: StrictBool = False
    voice: StrictBool = False
    subject_permission_attested: StrictBool = False
    expires_at: datetime


class ApproveVoicePersonRequest(PersonEnrollmentRequest):
    confirm_person_enrollment: StrictBool = False


class SessionNameRequest(Contract):
    name: Annotated[str, Field(min_length=1, max_length=80)]


class TrackBindingRequest(Contract):
    entity_id: UUID
    confirm_observed_object: StrictBool = False


class SaveObjectReferenceRequest(Contract):
    entity_id: UUID
    expires_at: datetime
    confirm_object_only_reference: StrictBool = False


class SaveFaceReferenceRequest(Contract):
    entity_id: UUID
    confirmed_name: Nonempty
    expires_at: datetime
    confirm_face_reference: StrictBool = False


def create_app(
    repository: EntityRepository | None = None,
    token: str | None = None,
    layout: RuntimeLayout | None = None,
    capture_factory: Callable[..., CaptureSession] | None = None,
) -> FastAPI:
    configured_token = token or os.environ.get("MNEMOS_OWNER_TOKEN", "")
    repo = repository or EntityRepository(
        os.environ.get(
            "MNEMOS_DATABASE_URL", "postgresql+psycopg://mnemos:mnemos@127.0.0.1:5432/mnemos"
        )
    )

    capture_factory = capture_factory or build_capture
    capture: CaptureSession | None = None
    capture_lock = asyncio.Lock()
    owner_principal = uuid5(NAMESPACE_URL, "mnemos:single-installation:owner")
    layout = layout or RuntimeLayout()
    references = ObjectReferences(repo, owner_principal, layout)
    face_references = FaceReferences(repo, owner_principal, layout)

    persons = PersonEnrollment(
        repo, owner_principal, BiometricKey(layout.path("data/security/biometric-key"))
    )
    registry = GovernedRegistry(repo, owner_principal)
    scheduler = TemporalScheduler(repo.engine, owner_principal)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        layout.configure()
        references.start()
        face_references.start()
        persons.start()
        scheduler.start()
        yield
        await scheduler.stop()
        await persons.stop()
        await references.stop()
        await face_references.stop()
        if capture is not None:
            await capture.stop()
        repo.close()

    app = FastAPI(
        title="Mnemos / Tobi",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    def owner(authorization: Annotated[str | None, Header()] = None) -> None:
        if len(configured_token) < 32:
            raise HTTPException(503, "owner authentication not configured")
        provided = authorization or ""
        if not secrets.compare_digest(provided.encode(), ("Bearer " + configured_token).encode()):
            raise HTTPException(401, "owner authentication required")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "running", "assistant": "Tobi"}

    @app.get("/ready", dependencies=[Depends(owner)])
    def ready() -> dict[str, str]:
        try:
            with repo.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            raise HTTPException(503, "database unavailable") from exc
        return {"database": "ready"}

    @app.get("/contracts/openapi.json", dependencies=[Depends(owner)])
    def contracts() -> dict[str, object]:
        return app.openapi()

    @app.post("/entities", response_model=Entity, status_code=201, dependencies=[Depends(owner)])
    def enroll(entity: Entity) -> Entity:
        try:
            return registry.save(entity)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(503, "registry unavailable") from exc

    @app.get("/entities", response_model=list[Entity], dependencies=[Depends(owner)])
    def entities(limit: Annotated[int, Query(ge=1, le=1000)] = 100) -> list[Entity]:
        try:
            return repo.list(limit)
        except SQLAlchemyError as exc:
            raise HTTPException(503, "registry unavailable") from exc

    @app.get("/entities/{entity_id}", response_model=Entity, dependencies=[Depends(owner)])
    def entity(entity_id: UUID) -> Entity:
        try:
            return repo.get(entity_id)
        except KeyError as exc:
            raise HTTPException(404, "entity not found") from exc
        except SQLAlchemyError as exc:
            raise HTTPException(503, "registry unavailable") from exc

    @app.put("/entities/{entity_id}", response_model=Entity, dependencies=[Depends(owner)])
    def update(entity_id: UUID, entity: Entity) -> Entity:
        if entity.id != entity_id:
            raise HTTPException(409, "entity id mismatch")
        try:
            return registry.save(entity, create=False)
        except KeyError as exc:
            raise HTTPException(404, "entity not found") from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(503, "registry unavailable") from exc

    @app.post(
        "/entities/{entity_id}/delete",
        response_model=ActionExecution,
        dependencies=[Depends(owner)],
    )
    def delete_entity(entity_id: UUID, request: DeleteEntityRequest) -> ActionExecution:
        try:
            return registry.delete(entity_id, request.confirmed_name, request.confirm_irreversible)
        except KeyError as exc:
            raise HTTPException(404, "entity not found") from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(503, "registry unavailable") from exc

    @app.get("/people", dependencies=[Depends(owner)])
    def people(
        response: Response, limit: Annotated[int, Query(ge=1, le=1000)] = 100
    ) -> list[dict[str, object]]:
        response.headers["Cache-Control"] = "no-store"
        try:
            return persons.people(limit)
        except SQLAlchemyError as exc:
            raise HTTPException(503, "person registry unavailable") from exc

    @app.post("/people", response_model=Entity, status_code=201, dependencies=[Depends(owner)])
    def enroll_person(request: PersonEnrollmentRequest) -> Entity:
        try:
            return persons.grant(
                request.name,
                face=request.face,
                voice=request.voice,
                subject_permission_attested=request.subject_permission_attested,
                expires_at=request.expires_at,
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(503, "person registry unavailable") from exc

    @app.get("/people/{entity_id}/consent", dependencies=[Depends(owner)])
    def person_consent(entity_id: UUID, response: Response) -> dict[str, object]:
        response.headers["Cache-Control"] = "no-store"
        try:
            return persons.status(entity_id)
        except KeyError as exc:
            raise HTTPException(404, "person consent not found") from exc
        except SQLAlchemyError as exc:
            raise HTTPException(503, "person registry unavailable") from exc

    @app.put("/people/{entity_id}/name", response_model=Entity, dependencies=[Depends(owner)])
    def rename_person(entity_id: UUID, request: RenamePersonRequest) -> Entity:
        try:
            return persons.rename(entity_id, request.name)
        except KeyError as exc:
            raise HTTPException(404, "person not found") from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(503, "person registry unavailable") from exc

    @app.post("/people/{entity_id}/revoke", dependencies=[Depends(owner)])
    def revoke_person(entity_id: UUID, request: DeleteEntityRequest) -> dict[str, str]:
        try:
            persons.revoke(
                entity_id, request.confirmed_name, confirmed=request.confirm_irreversible
            )
            return {"status": "revoked-and-deleted", "face_reference_cleanup": "pending"}
        except KeyError as exc:
            raise HTTPException(404, "person not found") from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(503, "person registry unavailable") from exc

    @app.post("/reminders", response_model=Reminder, status_code=201, dependencies=[Depends(owner)])
    def create_reminder(reminder: Reminder) -> Reminder:
        try:
            return scheduler.create(reminder)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(503, "reminder database unavailable") from exc

    @app.get("/reminders", response_model=list[Reminder], dependencies=[Depends(owner)])
    def reminders(limit: Annotated[int, Query(ge=1, le=1000)] = 100) -> list[Reminder]:
        try:
            return scheduler.reminders(limit)
        except SQLAlchemyError as exc:
            raise HTTPException(503, "reminder database unavailable") from exc

    @app.get("/notifications", dependencies=[Depends(owner)])
    def notifications(limit: Annotated[int, Query(ge=1, le=1000)] = 100) -> list[dict[str, object]]:
        try:
            return scheduler.notifications(limit)
        except SQLAlchemyError as exc:
            raise HTTPException(503, "notification inbox unavailable") from exc

    @app.get("/scheduler/status", dependencies=[Depends(owner)])
    def scheduler_status() -> dict[str, object]:
        return {
            "error": scheduler.error,
            "last_tick": scheduler.last_tick,
            "delivery": "local-dashboard-inbox",
        }

    @app.post("/capture/start", dependencies=[Depends(owner)])
    async def start_capture(request: CaptureRequest) -> dict[str, object]:
        nonlocal capture
        if request.mode == "native" and (
            (request.camera and not request.camera_consent)
            or (request.microphone and not request.microphone_consent)
        ):
            raise HTTPException(403, "explicit per-sensor consent required")
        if request.camera_index is not None and (request.mode != "native" or not request.camera):
            raise HTTPException(422, "camera index requires native camera capture")
        proposal = ActionProposal(
            kind="sensor_start",
            params=request.model_dump(),
            source_event_id=uuid4(),
            requested_by=owner_principal,
            confidence=1,
            risk=Risk.CONFIRMATION,
            provenance=Provenance(source_id="owner-dashboard", method="human"),
        )
        decision = PolicyEngine().evaluate(
            proposal, Authorization(owner_principal, True, confirmation=True)
        )
        if not decision.allowed:
            raise HTTPException(403, decision.reason)
        async with capture_lock:
            if capture is not None and capture.task is not None and not capture.task.done():
                raise HTTPException(409, "one active sensor session allowed; stop it first")
            try:
                capture = capture_factory(
                    request.mode,
                    request.camera,
                    request.microphone,
                    request.camera_consent,
                    request.microphone_consent,
                    transcribe=request.transcribe,
                    language=request.language,
                    camera_index=request.camera_index,
                )
                capture.start()
            except (ValueError, PermissionError) as exc:
                raise HTTPException(422, str(exc)) from exc
            return capture.snapshot()

    @app.post(
        "/capture/{capture_id}/enrollment/{proposal_id}/approve",
        response_model=Entity,
        status_code=201,
        dependencies=[Depends(owner)],
    )
    async def approve_voice_enrollment(
        capture_id: UUID, proposal_id: UUID, request: ApproveVoiceEnrollmentRequest
    ) -> Entity:
        if not request.confirm_catalog_enrollment:
            raise HTTPException(403, "explicit owner enrollment review required")
        if not request.name.strip():
            raise HTTPException(422, "entity name must not be blank")
        async with capture_lock:
            active = capture
            if active is None or active.id != str(capture_id) or active.state != "running":
                raise HTTPException(409, "capture session is no longer active")
            try:
                suggestion = active.enrollment.claim(proposal_id)
            except KeyError as exc:
                raise HTTPException(404, "enrollment proposal expired or unavailable") from exc
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
        succeeded = False
        try:
            value = Entity(
                id=suggestion.entity_id,
                kind="object",
                name=request.name.strip(),
                enrolled=True,
                confidence=1,
                provenance=Provenance(source_id="owner-voice-review", method="human"),
                retention=Retention(
                    scope="persistent", purpose="explicit reviewed object enrollment"
                ),
            )
            # Claim is the explicit owner action. Stop can immediately clear volatile
            # media during this bounded DB transaction; it does not revoke an already
            # confirmed manual mutation. Stable entity ID prevents duplicate retries.
            value = await asyncio.to_thread(
                registry.save, value, reviewed_proposal_id=suggestion.proposal.id
            )
            succeeded = True
            return value
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(503, "registry unavailable") from exc
        finally:
            active.enrollment.finish(proposal_id, succeeded=succeeded)

    @app.put("/capture/{capture_id}/faces/{track_id}/name", dependencies=[Depends(owner)])
    async def name_session_face(
        capture_id: UUID, track_id: UUID, request: SessionNameRequest
    ) -> dict[str, bool]:
        async with capture_lock:
            if capture is None or capture.id != str(capture_id):
                raise HTTPException(409, "capture session is no longer active")
            try:
                capture.name_face(track_id, request.name)
            except KeyError as exc:
                raise HTTPException(404, "face track unavailable") from exc
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
        return {"assigned": True, "persistent": False, "verified_identity": False}

    @app.post(
        "/capture/{capture_id}/enrollment/{proposal_id}/approve-person",
        response_model=Entity,
        status_code=201,
        dependencies=[Depends(owner)],
    )
    async def approve_voice_person(
        capture_id: UUID, proposal_id: UUID, request: ApproveVoicePersonRequest
    ) -> Entity:
        if not request.confirm_person_enrollment:
            raise HTTPException(403, "explicit owner person review required")
        async with capture_lock:
            active = capture
            if active is None or active.id != str(capture_id) or active.state != "running":
                raise HTTPException(409, "capture session is no longer active")
            try:
                suggestion = active.enrollment.claim(proposal_id)
            except KeyError as exc:
                raise HTTPException(404, "enrollment proposal expired or unavailable") from exc
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
        succeeded = False
        try:
            value = await asyncio.to_thread(
                persons.grant,
                request.name,
                face=request.face,
                voice=request.voice,
                subject_permission_attested=request.subject_permission_attested,
                expires_at=request.expires_at,
                entity_id=suggestion.entity_id,
                reviewed_proposal_id=suggestion.proposal.id,
            )
            succeeded = True
            return value
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(503, "person enrollment unavailable") from exc
        finally:
            active.enrollment.finish(proposal_id, succeeded=succeeded)

    @app.post(
        "/capture/{capture_id}/enrollment/{proposal_id}/reject", dependencies=[Depends(owner)]
    )
    async def reject_voice_enrollment(capture_id: UUID, proposal_id: UUID) -> dict[str, str]:
        async with capture_lock:
            if capture is None or capture.id != str(capture_id) or capture.state != "running":
                raise HTTPException(409, "capture session is no longer active")
            try:
                capture.enrollment.reject(proposal_id)
            except KeyError as exc:
                raise HTTPException(404, "enrollment proposal expired or unavailable") from exc
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
            return {"status": "rejected"}

    @app.post("/capture/{capture_id}/tracks/{track_id}/bind", dependencies=[Depends(owner)])
    async def bind_track(
        capture_id: UUID, track_id: UUID, request: TrackBindingRequest
    ) -> dict[str, object]:
        if not request.confirm_observed_object:
            raise HTTPException(403, "explicit observed-object confirmation required")
        async with capture_lock:
            active = capture
            if active is None or active.id != str(capture_id):
                raise HTTPException(409, "capture session is no longer active")
            try:
                claim = active.claim_track(track_id)
            except KeyError as exc:
                raise HTTPException(404, "track is stale or unavailable") from exc
            except PermissionError as exc:
                raise HTTPException(403, str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
        succeeded = False
        try:
            await asyncio.to_thread(
                authorize_binding,
                repo,
                owner_principal,
                capture_id,
                track_id,
                request.entity_id,
                confirmed=True,
            )
            succeeded = True
        except KeyError as exc:
            raise HTTPException(404, "enrolled object unavailable") from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(503, "registry unavailable") from exc
        finally:
            bound = active.finish_binding(
                track_id, request.entity_id if succeeded else None, claim["claim_id"]
            )
        return {"bound": bound, "scope": "human-session-track", "entity_id": str(request.entity_id)}

    @app.post(
        "/capture/{capture_id}/tracks/{track_id}/reference",
        dependencies=[Depends(owner)],
        status_code=201,
    )
    async def save_object_reference(
        capture_id: UUID, track_id: UUID, request: SaveObjectReferenceRequest
    ) -> dict[str, str]:
        if not request.confirm_object_only_reference:
            raise HTTPException(
                403, "explicit object-only reference persistence confirmation required"
            )
        async with capture_lock:
            active = capture
            if active is None or active.id != str(capture_id):
                raise HTTPException(409, "capture session no longer active")
        try:
            jpeg, provenance = await asyncio.to_thread(
                active.object_crop, track_id, request.entity_id
            )
            key = await asyncio.to_thread(
                references.store,
                request.entity_id,
                jpeg,
                provenance,
                request.expires_at,
                confirmed=True,
            )
            return {
                "id": str(key),
                "entity_id": str(request.entity_id),
                "scope": "explicit-object-reference",
            }
        except KeyError as exc:
            raise HTTPException(404, "bound object frame unavailable") from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except (SQLAlchemyError, OSError) as exc:
            raise HTTPException(503, "reference storage unavailable") from exc

    @app.get("/objects/{entity_id}/references", dependencies=[Depends(owner)])
    async def object_reference_list(entity_id: UUID, response: Response) -> list[dict[str, Any]]:
        response.headers["Cache-Control"] = "no-store"
        try:
            return await asyncio.to_thread(references.list, entity_id)
        except KeyError as exc:
            raise HTTPException(404, "object not found") from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(503, "reference database unavailable") from exc

    @app.post(
        "/capture/{capture_id}/faces/{track_id}/reference",
        status_code=201,
        dependencies=[Depends(owner)],
    )
    async def save_face_reference(
        capture_id: UUID, track_id: UUID, request: SaveFaceReferenceRequest
    ) -> dict[str, str]:
        if not request.confirm_face_reference:
            raise HTTPException(
                403, "explicit selected-person face persistence confirmation required"
            )
        async with capture_lock:
            active = capture
            if active is None or active.id != str(capture_id):
                raise HTTPException(409, "capture session no longer active")
        try:
            await asyncio.to_thread(
                face_references.check_person, request.entity_id, request.confirmed_name
            )
            jpeg, provenance = await asyncio.to_thread(active.face_crop, track_id)
            key = await asyncio.to_thread(
                face_references.store,
                request.entity_id,
                jpeg,
                provenance,
                request.expires_at,
                confirmed=True,
                confirmed_name=request.confirmed_name,
            )
            return {
                "id": str(key),
                "entity_id": str(request.entity_id),
                "scope": "explicit-consented-face-reference",
            }
        except KeyError as exc:
            raise HTTPException(404, "person or face frame unavailable") from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except (SQLAlchemyError, OSError) as exc:
            raise HTTPException(503, "face reference storage unavailable") from exc

    @app.get("/people/{entity_id}/face-references", dependencies=[Depends(owner)])
    async def face_reference_list(entity_id: UUID, response: Response) -> list[dict[str, Any]]:
        response.headers["Cache-Control"] = "no-store"
        try:
            return await asyncio.to_thread(face_references.list, entity_id)
        except KeyError as exc:
            raise HTTPException(404, "person unavailable") from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(503, "face reference database unavailable") from exc

    @app.get("/face-references/{reference_id}/image", dependencies=[Depends(owner)])
    async def face_reference_image(reference_id: UUID) -> Response:
        try:
            jpeg = await asyncio.to_thread(face_references.read, reference_id)
            return Response(jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})
        except KeyError as exc:
            raise HTTPException(404, "face reference unavailable") from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except (SQLAlchemyError, OSError) as exc:
            raise HTTPException(503, "face reference unavailable") from exc

    @app.post("/face-references/{reference_id}/delete", dependencies=[Depends(owner)])
    async def face_reference_delete(
        reference_id: UUID, request: DeleteEntityRequest
    ) -> dict[str, str]:
        try:
            await asyncio.to_thread(
                face_references.retire,
                reference_id,
                request.confirmed_name,
                confirmed=request.confirm_irreversible,
            )
            return {"state": "access-revoked-cleanup-pending"}
        except KeyError as exc:
            raise HTTPException(404, "face reference unavailable") from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except (SQLAlchemyError, OSError) as exc:
            raise HTTPException(503, "face reference revocation unavailable") from exc

    @app.get("/face-references/status", dependencies=[Depends(owner)])
    async def face_reference_status() -> dict[str, str | None]:
        return {"cleanup_error": face_references.error}

    @app.get("/references/{reference_id}/image", dependencies=[Depends(owner)])
    async def reference_image(reference_id: UUID) -> Response:
        try:
            jpeg = await asyncio.to_thread(references.read, reference_id)
            return Response(jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})
        except KeyError as exc:
            raise HTTPException(404, "reference not found") from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(503, "reference database unavailable") from exc

    @app.post("/references/{reference_id}/delete", dependencies=[Depends(owner)])
    async def delete_reference(reference_id: UUID, request: DeleteEntityRequest) -> dict[str, str]:
        try:
            await asyncio.to_thread(
                references.retire,
                reference_id,
                request.confirmed_name,
                confirmed=request.confirm_irreversible,
            )
            return {"status": "access-revoked-cleanup-pending"}
        except KeyError as exc:
            raise HTTPException(404, "reference not found") from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(503, "reference database unavailable") from exc

    @app.get("/references/status", dependencies=[Depends(owner)])
    def reference_retention_status() -> dict[str, str | None]:
        return {"error": references.error, "cleanup": "bounded-local-worker"}

    @app.post("/capture/stop", dependencies=[Depends(owner)])
    async def stop_capture() -> dict[str, object]:
        async with capture_lock:
            if capture is None:
                return {"state": "idle", "recording": False}
            await capture.stop()
            return capture.snapshot()

    @app.get("/capture/status", dependencies=[Depends(owner)])
    def capture_status(response: Response) -> dict[str, object]:
        response.headers["Cache-Control"] = "no-store"
        return capture.snapshot() if capture else {"state": "idle", "recording": False}

    @app.get("/capture/frame", dependencies=[Depends(owner)])
    def capture_frame() -> Response:
        if capture is None:
            raise HTTPException(404, "no live frame")
        with capture.lock:
            jpeg = capture.jpeg
        if jpeg is None:
            raise HTTPException(404, "no live frame")
        return Response(jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    return app
