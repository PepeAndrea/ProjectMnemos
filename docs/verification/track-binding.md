# Explicit object-track association verification — 2026-10-08

T017 partial: an enrolled owner catalog object can be explicitly associated to a currently
visible non-person track. UI numbers correspond to overlay numbers; name overlays say
confermato da te and distinguish detector confidence. No reference image is saved.

Unit/API tests cover owner authentication, strict/default-false confirmation, foreign/unavailable
entities, person/face tracks, freshness, duplicate claim, DB failure with safe retry, ID-only audit,
stop cleanup, missed detection removing binding and old completion unable to consume a newer
claim. No persistence or privilege follows solely from detector/ASR confidence.
PostgreSQL binding audit is tested in test_track_binding_* isolated schemas, dropped at exit.

Benchmark: python -m mnemos.track_binding_benchmark, 100 synthetic associations, never starts
a device. p95 claim/finish 0.0084ms, isolated SQLite audit 0.832ms. Temporary DB removed at exit;
runtime/exports/track-binding-benchmark.json. This is not recognition accuracy or full-frame latency.
Production web build passes (33 modules); contracts export includes the new policy action.

Browser: isolated 5181, SQLite, synthetic token, generated rectangle pixels and fixed synthetic
backpack detector. Registered synthetic catalog name; observed numbered track; submission disabled
without explicit checkbox; confirmed association displayed on overlay with detector confidence.
Stop removed feed/association and preserved catalog. Restart requires a new selection. Screenshot
runtime/exports/track-binding-dashboard.jpg. No camera/microphone permission or real image used;
this browser check verifies orchestration/UI, not actual model detection accuracy.

All five canonical Drive modified timestamps rechecked and match the verified mirror; no push.
Remaining: authorized sample acquisition, physical references and calibrated recognition on
reappearance. No additional task/epic/milestone declared Done.

Final suite: 103 passed, no skips with installed local models/speech and PostgreSQL opt-in;
Ruff, format, strict mypy (45 sources), eight mirror hashes and replay pass. The final claim-token
race regression passes; failed DB retry cannot retain a binding. Browser restart showed anonymous
backpack track 1 with unchecked confirmation while the catalog name remained; Disconnect cleared
private UI state. The synthetic server is stopped after verification, fixture DB retained locally.

Selection form also clears track/name confirmation when the selected track or catalog entity
vanishes from current props, so a returning option does not reuse a retained checkbox. Final
TypeScript/production build passes with this invalidation; saved overlay layout remains unchanged.
