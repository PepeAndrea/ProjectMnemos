# Explicit object references — core API

Reference dashboard controls are pending. Current server workflow: register a catalog object,
start an explicitly authorized source, select its current non-person track and confirm /bind.
Then POST /capture/{capture_id}/tracks/{track_id}/reference with entity_id, aware future expires_at
and confirm_object_only_reference=true. No bytes, paths, boxes or source IDs can be supplied.

Inspect the selected object: it must be fully visible, at least 32px and clear of people/faces.
Detected overlaps reject; detection is not exhaustive privacy verification. This endpoint never
enrolls a person. Keep subject consent, sensor permission and conversation recording separate.
Only the selected crop persists; general capture stays non-recording. Expiry cannot outlive an
entity deadline. Budget overflow rejects until explicit deletion/retention cleanup frees storage.

GET /references/{id}/image requires the owner bearer and produces audited no-store JPEG; do not
publish a raw/static reference URL. POST /references/{id}/delete requires confirmed_name matching
the current object name and confirm_irreversible=true. The response access-revoked-cleanup-pending
means logical access is already denied and the worker will unlink the ciphertext. GET
/references/status exposes a sanitized cleanup error; storage outage never extends read access.

runtime/data/security/reference-key is distinct from biometric-key, regular owner-only 0600.
Preserve its original bytes with an appropriate future encrypted backup design. Existing metadata
or ciphertext plus missing key cannot be recovered by generating a replacement. Never log,
commit or upload key material. File unlink does not erase WAL/backups/OS caches; abrupt death
before DB commit may leave inaccessible orphan ciphertext. Reconciliation/rotation remain pending.

Use python -m mnemos.reference_benchmark for contained synthetic overhead checks; it never starts
native sensors. Live quality and automatic recognition on reappearance are not yet validated.

Dashboard controls are now available (supersedes the initial pending note above): after binding a
track, choose it under Salva una reference dell’oggetto, set an explicit local deadline, verify
object-only contents in the live feed and check the persistence confirmation. Salva reference
corrente stores the current server crop at click time. In Reference degli oggetti, choose the
catalog object and Mostra reference to fetch its saved crop. Nascondi reference releases the
preview; Disconnect clears private page state. Saved references remain after capture Stop.

Revoca e cancella reference requires the current exact object name and explicit irreversible
confirmation. Browser automation verification tests these gates without submitting final deletion;
backend/live HTTP synthetic tests verify actual revocation and physical cleanup. Do not equate
reference existence with calibrated identity matching. Development factory injection supports
isolated synthetic sources without modifying global API behavior or enabling native sensors.

Save several distinct views. New reference rows report crop dimensions and basic contrast,
detail and exposure warnings. Review the image and improve light/view if warnings occur;
no warning is not proof of sharpness or correct physical identity. Legacy images display
quality-not-evaluated. Essentially featureless black/white crops reject before persistence.
Identical newly stored image bytes for the same object reject: acquire a different view.
Byte-different near-duplicates or actual pose diversity are not yet validated. Each saved
view can be revoked independently. Use reference_quality_benchmark for generated diagnostic
checks; its figures are not representative quality/identity accuracy.
