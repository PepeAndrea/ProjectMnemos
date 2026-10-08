# ADR-029 — Bounded object-reference diagnostics and duplicate-view rejection

Accepted 2026-10-08. T018 partial implementation after verified T017 (ADR-028).
Actual person-view acquisition, pose/diversity validation and representative quality
calibration remain required; this change does not complete T018 or physical matching.

Compute versioned quality diagnostics from the server-selected object crop before JPEG
encoding: grayscale mean/standard deviation, mean adjacent-pixel difference and
saturated-pixel fraction. Area-resize large crops to at most 256px on the longest side
for approximate aggregates without full-resolution derivative arrays. Keep encoded crop
dimensions separately. These are provisional measurements, not a sharpness/identity score:
smooth objects can have little detail, and noise high edge energy. Never use this alone
for identification or enrollment confidence.

Reject an essentially featureless black/white sample (std <=1 and luma <=2 or >=253)
before storage/key creation. Other low contrast/detail and strongly clipped exposure
produce warnings. Keep plain colored objects reviewable. UI reports dimensions and
warnings with each reference, allows explicit preview, and explains that no warning
certifies quality or view diversity. Legacy references display quality-not-evaluated.

Quality metadata is encrypted-envelope AAD. Reject identical newly stored JPEG bytes
for the same entity while an active reference exists. Store an entity-bound HMAC-SHA256
content tag using the private reference key, never expose it via listing/audit. This
avoids adding a publicly guessable image digest. Legacy untagged references are not
retroactively hashed; byte-different copies/view similarity remain later work. Duplicate
rejection rolls back audit/DB and writes no extra file/link. Revoking one view leaves
the others accessible.

Alternatives measured on M1: six synthetic cases, 50 runs each. 128px sharp/blurred/plain
crops p95 ~0.09–0.10ms; black/white reject ~0.04–0.05ms. The 1600px area-resampled path
costs 15.15ms p95 versus 11.30ms for full-resolution derivative measurement. Choose bounded
auxiliary memory, not speed: derived gray/float/difference measurements use 65,536 pixels
instead of 2,560,000. Both timings fit the overlay engineering budget; selected source/crop
bytes still exist separately. Generated fixtures establish no representative calibration.

Integrated 50-crop synthetic benchmark: p95 crop+quality 0.349ms, store/audit 3.574ms,
read/audit 2.529ms, retire/purge/audit 4.974ms. Actual isolated HTTP/PostgreSQL verified
two different views, diagnostics, black/duplicate rejection, independent revocation and
cleanup. Isolated browser verified warning text, preview after Stop and Disconnect
clearing private state. No extra package/model/migration/cloud call/real subject/native sensor.
