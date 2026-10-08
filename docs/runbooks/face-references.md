# Consented face reference images

Register the person with independently valid face permission and a future consent deadline.
Start capture, select a currently observed face and that enrolled person, enter an image deadline
within consent and explicitly confirm saving only that face crop for the selected person.
The server rechecks consent/name after cropping. A selected label does not verify identity.

The authorized-face reference panel lists the person's active images and opens an authenticated
no-store preview. Stop clears live tracks; an explicitly saved image remains until its deadline
or revocation. Revoking consent immediately denies all image reads and schedules deletion.
Individual deletion requires current name and irreversible confirmation. Cleanup failure retains
an inaccessible tombstone for retry; status is exposed through /face-references/status.

runtime/data/security/face-reference-key is a separate lazy 32-byte key (0600, parent 0700).
Preserve original keys for recovery; never replace a missing key to regain existing ciphertext.
No production face sample/key was created during synthetic verification. Images are encrypted
under runtime/media/evidence/face-references; no public static route. Audits contain IDs only.

Do not infer recognition accuracy, automatic identity approval or recording authorization from
this acquisition path. Quality/pose acceptance and calibrated matching are still pending.

New references also report uncalibrated eye-line geometry and image detail. Missing geometry
is explicitly non valutata; legacy images are not reprocessed automatically. Warnings invite
a clearer/additional frontal view without forbidding useful profiles. See ADR-031.
