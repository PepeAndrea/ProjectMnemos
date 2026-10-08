# ADR-023 — Server-owned voice proposals and explicit owner review

Accepted 2026-10-08. T017 partial implementation; complements ADR-022.

Final local ASR now feeds a bounded VoiceEnrollmentInbox inside the active capture session.
A narrow deterministic IT/EN grammar proposes catalog object names for “memorizza questo
come …” / “remember this as/is …”. It accepts the observed Whisper spelling “Toby” as an
address variant; the assistant remains Tobi. Addressing Tobi is not speaker authentication.
No wake word is mandatory for these suggestions. This is not general natural-language intent
extraction, speaker recognition, or physical instance enrollment.

Only server-owned final updates are eligible. Partials, expired/future timestamps, non-finite
scores, quotations, negation prefixes, multi-clause punctuation and unsupported actions are
rejected. No endpoint accepts client transcripts, speaker IDs/scores or caller authority flags.
ASR confidence is displayed as transcription evidence and grants no command authority.
The anonymous ActionProposal is denied by PolicyEngine even with perfect transcription
confidence. The authenticated owner must review/correct the name and explicitly confirm
catalog persistence. Reviewed creation then uses the existing policy + transactional audit;
entity provenance is human owner-voice-review. Audit links the volatile source proposal UUID,
without copying transcript, anonymous speaker ID, name or audio.

Pending suggestions cap at 50, dedup history at 200 and lifetime at five minutes from the final
utterance timestamp. Stop, source failure and global EOF clear suggestions with media/text.
A deterministic entity UUID per capture/utterance prevents duplicate durable creations even
after the bounded dedup cache evicts an old marker. Concurrent approvals claim the proposal
once; failed DB writes restore it only if still present/unexpired. Consumed/rejected/stale
proposals cannot be approved again in the current inbox.

A claimed, explicitly confirmed owner mutation runs in a bounded DB worker independently of
capture stop. Stop immediately clears volatile media, and does not revoke a catalog action the
owner already confirmed. Completion/retry cannot resurrect the cleared inbox. This avoids
holding the capture lock while DB I/O blocks. Stable entity IDs also prevent duplicate writes
when the client loses the response; the owner can refresh the catalog.

Decision: use Level-0 routing for this bounded command before introducing a cloud extractor.
This grammar has measurable scope and no extra dependency, model, cloud call or speaker
privilege. Semantically broader commands remain for the extraction/routing plan; they must
retain the same action/identity boundary. Owner review also permits correction of observed
Whisper substitutions instead of treating raw ASR text as a correct entity label.

Evidence: 92 full-suite tests pass with actual local models/speech/PostgreSQL, none skipped;
tests/test_voice_enrollment.py and test_api.py cover parsing, authorization, TTL/bounds,
dedup eviction, failure retry, concurrent approval and immediate stop during a blocked DB
write. Live Whisper → HTTP → PostgreSQL synthetic verification: proposal 3447ms including
model preparation, explicit owner review/create 35.2ms, one linked audit; stop leaves no
transcripts/proposals, fixture removed. Synthetic router p95 0.00105ms, offer p95 0.0269ms,
50-item snapshot/policy checks p95 0.226ms. No representative language-accuracy claim.

Production dashboard bundle verified on an isolated synthetic server: final proposal,
unchecked confirmation blocking submission, corrected name registration, linked audit,
reload persistence and Disconnect clearing private UI state. Human catalog entries display
“Nome confermato”; their confidence is not physical recognition accuracy.

Remaining T017: dedicated authorized-person consent/enrollment/revocation, actual physical
reference acquisition and integrated canonical acceptance. Speaker enrollment/recognition
and general intent extraction remain their own planned work. No epic/milestone is complete.
