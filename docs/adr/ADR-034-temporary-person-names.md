# ADR-034 — Automatic temporary person names

Accepted 2026-10-09 for the explicit request to approve people automatically and associate
names from audio or the panel. This implements session display annotations. It does not
complete persistent enrollment or biometric matching, which retain their independent consent
and evidence requirements.

Local final IT/EN introductions (`mi chiamo`, `questa persona si chiama`, `my name is`,
`this person is called`) can automatically annotate a sole face continuously visible during
the utterance. Input must be fresh (five seconds), final, finite and confidence >=0.8.
The grammar is anchored and bounded; quoted/negative/chained clauses are rejected. The ASR
score is a provisional routing guard, not calibrated identity confidence. The visible label
explicitly says `nome provvisorio`. Sound may come from an off-camera speaker: this path
never claims speaker identity, enrolls an entity, stores biometrics or grants command authority.

The authenticated panel can select a currently visible face and set/correct its name directly,
without a second approval. Audio never overwrites an owner correction or an existing label.
Labels expire on any missed face observation, two seconds without new observations, stop,
source failure or session end. They are held only in bounded process memory; no DB writes,
images, embeddings, audit text or cross-session identity links are created. Deduplication is
bounded to 200 utterance IDs; tracks use the existing 128-track bound. Reappearance requires a
new annotation. Multiple faces, a changed face during speech and low confidence stay unnamed.

Alternatives: guessing persistent identities from anonymous speech was rejected because a
transcript is not verified speaker identity or subject consent. Replacing Tiny with Base solely
for one name was tested and rejected: the synthetic `Mi chiamo Andrea` fixture was misheard by
both (scores 0.549 and 0.485). Preserve this negative evidence rather than lowering the guard.
The panel is the correction path; model accuracy remains a downstream acceptance requirement.

Validation: tests/test_session_names.py exercises ambiguity, freshness, overwrite protection,
loss, failure, API authentication and absence of catalog writes. Actual YuNet/Silero/Whisper
replay and bounded routing benchmark: runtime/exports/session-names-replay.json. Negative ASR
spike: runtime/exports/session-names-italian-spike.json. Synthetic UI manual assignment and
Stop: runtime/exports/session-names-dashboard.jpg. No real person/sensor was used in these tests.
