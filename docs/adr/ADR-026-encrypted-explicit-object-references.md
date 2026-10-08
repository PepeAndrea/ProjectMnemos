# ADR-026 — Explicit cropped object references in encrypted local media storage

Accepted 2026-10-08. T017 basic enrollment support; does not complete dependent multiview,
embedding, feature verification or integrated physical recognition tasks.

A catalog name and session track binding are insufficient for later physical matching. The
server now supports an explicit reference-save action from a fresh owner-bound object track.
It selects the corresponding normalized source/sequence, validates full visibility and a 32px
minimum crop, then encodes only that region (maximum dimension 1600, JPEG <=2MiB). Object crops
intersecting detected people/faces reject; move the object to a clear view. This detection guard
is not proof that all people/private content were detected; the owner must explicitly confirm
object-only persistence. Persistent people use the separate consent path, not this route.

Use encrypted local files behind ObjectReferences, with DB metadata/reference IDs rather than
DB blobs or public media URLs. A separate reference-key is lazily created using the audited
private-key loader from ADR-024; AESGCM envelopes bind reference/entity IDs, byte count,
provenance, owner and requested expiry. Folder 0700, UUID-derived files 0600 and no final symlink
following; bytes never go to static hosting or cloud. Missing key with existing metadata/files
refuses regeneration. Limits: 20 references/object, 512 encrypted files or 64MiB total storage;
reject budget overflow rather than silently evicting owner-approved references.

Persistence requires explicit confirmation and an aware future deadline no later than the
entity's deadline. Selection comes exclusively from server-held current frame; no endpoint
accepts uploaded bytes, boxes, class labels or claimed source. Save/read/delete/expire go through
PolicyEngine; reads commit an ID-only access audit before returning JPEG with no-store.
Human enrollment confidence is not physical recognition accuracy. Capture Stop clears latest
raw frame and buffers but does not undo an already explicitly selected save operation.

File creation precedes DB reference/entity/audit commit. Ordinary transaction failure removes
the newly created ciphertext and leaves no entity reference. Filesystem and DB cannot share one
atomic transaction; abrupt process death may leave an orphan ciphertext. It remains inaccessible
without committed metadata and counts against storage budget. Automatic orphan reconciliation
and encrypted backup/WAL lifecycle remain later work; do not claim crash-proof physical erasure.

Revocation uses exact current object name plus strong confirmation. It atomically removes the
entity reference and marks metadata pending-deletion. A bounded local worker unlinks ciphertext
then removes the tombstone; filesystem failure retries while access stays denied. Expiry access
checks are immediate, with pre-authorized bounded cleanup (100 rows/batch). Missing ciphertext
or insecure/tampered envelope fails closed. Successful active-file unlink is not forensic erasure
of OS caches/backups; key rotation/Keychain isolation remain future security work.

Measured 50 synthetic 128px crops on M1: p95 crop 0.100ms, encrypted store+audit 1.843ms,
read+audit 1.171ms, retire/purge+audit 2.317ms using isolated SQLite/files. No extra package/model.
Tests include authenticated server crop API, person overlap/staleness/source mismatch, forbidden
client uploads, encryption/private permissions, metadata tampering, audit rollback, immediate
expiry denial, filesystem cleanup retry and actual PostgreSQL isolated-schema roundtrip.

T017 remains In Progress: dashboard save/preview/delete controls, authorized-person sample
acquisition, physical quality validation and complete integrated acceptance remain outstanding.
T018–T022 are not promoted or bypassed by the basic reference primitive.

2026-10-08 follow-up: dashboard controls now save the current server-selected bound crop with
blank-by-default deadline and separate unchecked object-only persistence confirmation. The UI
states that this is the current crop, not a frozen preview of an earlier frame. Owner-only metadata
list and audited no-store image fetch support lazy preview; only one blob image is held, URLs
revoked on hiding, expiry, object/token changes, disconnection or unavailable metadata. Request
abort/generation guards prevent stale responses restoring cleared previews; exact-name/strong
revocation remains required. This completes the basic object-reference UI, not physical matching.

Live synthetic loopback HTTP + isolated PostgreSQL: crop dimensions 96x96 (not full 128x128),
private encrypted file, save 16.81ms, readable after capture Stop, immediate revoked-read denial,
physical cleanup 605.82ms. Audits: create/bind/store/delete one each and three reads; no name in
audit. Schema/files/key/server are isolated and cleaned. Source/detector are generated stubs,
so this is real orchestration/storage verification and not model or recognition accuracy.
