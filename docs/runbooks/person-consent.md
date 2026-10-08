# Local person consent and revocation

Connect as the installation owner. In Persone autorizzate, enter the person's name, select
only the permitted face/voice scopes, specify a future local deadline, and attest explicit subject
permission. Both scopes and attestation start unchecked. Registration stores consent metadata;
it does not capture a sample, independently validate consent or authorize the person to command
Tobi. Camera/microphone and conversation recording permission remain separate.

Alternatively, an active local transcript can propose a name with the narrow enrollment
command. In Proposta vocale da rivedere, select Persona autorizzata, correct the proposed
name, select face/voice scope, enter the consent deadline, attest permission and confirm
the catalog registration. The original speaker remains anonymous; the chosen name is
your reviewed catalog label, not a verified identity inferred from that utterance.
Stop or session expiry removes unreviewed proposals. A confirmed transaction already
in progress may finish after Stop, but cannot restore the cleared private transcript.
Automatic approval is not currently enabled; its requested scope is pending clarification.

The dedicated list displays modality scopes and expiry. Rename updates only the display name.
Revocation requires the current exact name and explicit irreversible confirmation; it removes
active identity/template DB rows atomically with an ID-only audit. Expiry denies access immediately
and automatic bounded cleanup removes rows. Database outage can delay physical cleanup, never
extend access authorization. Audit/consent tombstones retain minimal identifiers and dates.

No public template upload/read API exists. Explicit consent-bound face image reference acquisition
is available (see face-references.md); matching provider integration and real authorized acquisition
verification are still pending. Never use arbitrary passerby images/voice for enrollment or assert recognition
accuracy from the synthetic storage benchmark.

When first authorized template storage is enabled, runtime/data/security/biometric-key contains
the 32-byte installation key, owner-only 0600 with 0700 directory. Preserve it separately from the
DB; existing encrypted rows cannot be recovered by generating a replacement. A missing key with
existing ciphertext fails closed. Restore the original key and permissions; do not auto-rotate,
print it, commit it or upload it. Backup/rotation and Keychain integration are not implemented.
Active-row deletion does not securely erase WAL/backups or plaintext already held by a caller;
future gallery providers must invalidate cached vectors on revocation. See ADR-024.

The loopback port-5180 verification server uses runtime/tmp/ui-registry-test.db and a synthetic
token, not runtime/data PostgreSQL or the installation owner token. Manually entered metadata in
that test DB remains there for continuity; do not treat it as production enrollment.
