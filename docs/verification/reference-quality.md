# T018 reference quality progress — 2026-10-08

T018 remains In Progress: object-crop measurements and multiple encrypted views are
implemented, not authorized person acquisition or physical pose/diversity/accuracy.
Prerequisite T017 audited in ADR-028; design/limits in ADR-029.

Tests cover black/white rejection, plain-object warnings, sharp/blurred generated
diagnostics, bounded large-crop sampling, invalid dimensions/format, no reference/key
on no-signal failure, two views after Stop and independent retirement. HMAC duplicate
guard refuses an extra file/link and never exposes the tag. Existing expiry, encryption,
audit rollback and revoked-access checks pass.

Full suite after implementation: 116 passed, no skips with actual local models/speech
and PostgreSQL opt-ins. Ruff/format/strict mypy (51 source files), eight mirror hashes
and replay pass. After adding the comparison benchmark, the same 116 tests passed again
with strict mypy covering 52 source files. Production TypeScript/Vite build passes (35 modules).

`python -m mnemos.reference_http_verify`: real loopback HTTP and isolated PostgreSQL
with synthetic source/detector, two distinct generated 96px JPEG crops, quality metadata,
duplicate/all-black 422 responses, remaining-view survival after first revocation, then
both files removed in ~679ms. First save ~21.70ms; two stores/two deletes/five audited
reads plus create/bind. Schema/files/key/server cleaned. No production data/device touched.

`python -m mnemos.reference_quality_benchmark`: six generated crops, 50 measurements
each; bounded 1600px input p95 15.15ms versus full-resolution alternative 11.30ms,
39 times fewer pixels in derived arrays. 128px accepted samples p95 <=0.104ms. These
are synthetic behaviors/overhead, not calibrated quality accuracy. Integrated 50-crop
benchmark p95 crop 0.349ms/store 3.574ms/read 2.529ms/retire 4.974ms. Reports under runtime/exports.

Browser 5183 used fresh isolated SQLite/root and synthetic token/pixels/detector only.
UI saved explicit 120px reference, displayed “contrasto basso, pochi dettagli visibili”,
retained preview after Stop, and removed gallery/token/blob on Disconnect. No final
destructive UI action. Server stopped normally; fixture retained runtime/tmp/ui-quality-test*.
Proof: runtime/exports/reference-quality-dashboard.jpg.

Remaining: valid-consent person acquisition, measured physical acquisition quality and
representative fixtures, multiview/pose distinction, matching and integrated M2 exit.
