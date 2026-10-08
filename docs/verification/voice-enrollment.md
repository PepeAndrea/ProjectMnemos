# Reviewed voice enrollment verification — 2026-10-08

T017 remains In Progress. The active capture pipeline produces temporary object-name
suggestions from final server-owned ASR updates. Every anonymous speech proposal fails
policy authorization; no entity is written until authenticated human review and confirmation.
The UI permits correction and rejection and explains that physical evidence capture is separate.

Verified boundaries:
- IT/EN narrow anchored grammar, observed ASR address variant, no mandatory wake word;
  quotations, negation, chained clauses, non-enrollment actions, blanks and oversize input reject.
- No client transcript/speaker authority fields; strict confirmation rejects strings/omission.
- Partial/final, five-minute expiry, 50 pending / 200 history bounds, dedup and deterministic
  durable IDs, consumed/rejected/stopped session rejection.
- SQL failure → proposal retry + no entity; concurrent claims reject; an explicit mutation
  can finish during stop without delaying stop or resurrecting volatile names/transcripts.
- Reviewed name/actor/provenance stored through GovernedRegistry with linked atomic audit;
  source proposal UUID only, no full transcript, audio or anonymous speaker persistence.

`MNEMOS_TEST_MODELS=1 MNEMOS_TEST_SPEECH=1 MNEMOS_TEST_POSTGRES=... scripts/check`:
92 passing tests, no skips, Ruff/format/strict mypy/eight mirror hashes/replay pass.
`pnpm --dir apps/web build`: TypeScript + production bundle passed, 31 modules.

`python -m mnemos.voice_enrollment_benchmark`: 1000 synthetic grammar/offer operations,
100 snapshots; route p95 0.00105ms, offer 0.0269ms, snapshot 50 proposals/policies 0.226ms.
Output runtime/exports/voice-enrollment-benchmark.json. This is narrow routing overhead,
not representative semantic/speaker/ASR accuracy.

`python -m mnemos.voice_enrollment_verify`: opt-in idle core, generated synthetic English
fixture and installed Whisper. Real loopback HTTP + PostgreSQL produced a denied anonymous
proposal in 3447ms, accepted explicit reviewed name in 35.2ms with one linked audit. Stop
cleared proposals/transcripts; this run's unique synthetic entity and audit were removed.
Output runtime/exports/voice-enrollment-http.json. No native camera/microphone or cloud call.
Never run this harness against a non-idle core or replace its fixed synthetic replay source.

Browser verification: isolated port 5180, SQLite fixture, synthetic token and server-owned
synthetic final update; native sensors disabled. Observed unchecked confirmation/disabled
registration, owner correction, catalog persistence, one linked audit, reload and Disconnect
clearing token/catalog/transcripts. Screenshot runtime/exports/voice-enrollment-dashboard.jpg.
ASR correctness was verified separately by the real loopback test above. Temporary UI server
is stopped after review. The screenshot is exclusively synthetic state.

Drive metadata rechecked for all five canonical files; modified timestamps match the verified
mirror. No canonical publish or biometric acquisition performed.
Remaining: authorized people/consent/revocation, physical reference capture/instance matching,
representative calibration, general intent extraction and the complete first vertical slice.
