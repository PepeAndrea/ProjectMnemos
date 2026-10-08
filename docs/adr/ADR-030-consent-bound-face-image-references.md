# ADR-030 — Consent-bound face image references

Status: accepted, 2026-10-08. Scope: partial T018; no identity matching claim.

Reuse the bounded encrypted object-reference storage primitive, with a separate face table,
private key, consent provenance and authorization hooks. Compared with DB blobs or a new media
service, this avoids another runtime and preserves the tested rollback, expiry and deletion
behavior. Dedicated face metadata prevents generic object routes from exposing biometric media.

Acquisition requires installation-owner authentication, explicit selection and confirmation of
the enrolled person's current name, active face consent and a deadline within that consent.
The server selects a fresh face track, validates its source/sequence and crops its current frame.
Reject partial, stale, under-64px or overlapping-face crops. These provisional guards do not prove
subject identity or exclude undetected bystanders. Tracks remain anonymous; acquisition does not
bind a name to a live track or enable recognition. Voice-only consent cannot authorize this route.

Lock consent before entity/reference rows. Revocation marks all face references inaccessible in
the same transaction as consent/template revocation; bounded asynchronous filesystem cleanup
retries failures. Reads validate current consent and provenance and commit ID-only audit before
returning plaintext. Expiry denies access even when cleanup fails. No whole-frame recording.

Limits: 20 images/person, 512 files and 64MiB per face store, 2MiB/image, 1600px longest edge.
Separate lazy AES-GCM key; missing key with existing data fails closed. Quality diagnostics and
private exact-duplicate checks reuse ADR-029. No public upload or template endpoint.

M1 synthetic benchmark (50 generated 128px crops): p95 crop 0.35ms, audited store 3.55ms,
read 1.85ms, retire/purge 3.19ms. Actual isolated HTTP/PostgreSQL two-view flow passed:
save 68.46ms, consent-revocation cleanup 865.02ms. This supports the implementation choice,
not biometric quality/accuracy. See docs/verification/face-references.md.

Remaining: real authorized acquisition, pose/diversity criteria, representative quality,
landmark alignment and matching providers. T018 stays In Progress. Crash orphan reconciliation,
key backup/rotation and secure erasure of WAL/backups remain separate work.
