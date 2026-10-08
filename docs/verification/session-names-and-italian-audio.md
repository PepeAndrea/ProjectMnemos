# Temporary person names and Italian audio

2026-10-09: 168 tests passed with MNEMOS_TEST_MODELS=1, MNEMOS_TEST_SPEECH=1 and the local
MNEMOS_TEST_POSTGRES URL. No skips. Ruff/format/mypy (63 sources), eight mirrored source hashes,
contract replay and web build passed. Only the existing Starlette TestClient deprecation remains.

`python -m mnemos.session_names_replay` regenerates synthetic local macOS speech and replays it
through real YuNet, Silero, Whisper and CaptureSession against the hash-pinned fictional image.
No camera/microphone, person enrollment, cloud call or persistent identity write is involved.
Its report is runtime/exports/session-names-replay.json. The narrower grammar benchmark is not
representative identity accuracy. The negative Italian-name spike preserves inaccurate ASR
outputs/scores in runtime/exports/session-names-italian-spike.json. Tiny and Base both misheard
`Mi chiamo Andrea`; no threshold was lowered to force that case through.

Isolated synthetic UI on 5187: connect -> replay -> select sole face -> assign name directly ->
visible `Andrea dal pannello · nome provvisorio` -> Stop removes preview, annotation controls
and transcript. Screenshot runtime/exports/session-names-dashboard.jpg. Native sensor checkboxes
remained unchecked. Existing installation entities were untouched.

Italian is explicitly sent by the dashboard and is the API/provider default. Explicit-English
regression fixtures remain supported. Unsupported autodetected languages are dropped per segment;
errors carry sanitized static codes. The original live speech failure lacked a retained subtype;
its cause remains unconfirmed. The core was restarted with sensors idle to load these changes.

Actual integrated positive replay completed after final fixture update: Italian name Maria at
4094.659ms, English name Alice at 3529.496ms; routing offer p95 0.0294ms (1000 samples).
These are synthetic checks, not false-identity-rate calibration. Isolated UI additionally
confirmed automatic `Maria · nome provvisorio` from Italian final speech, then Stop/disconnect:
runtime/exports/session-names-automatic-italian.jpg. Test server stopped normally afterward.

Actual development core HTTP replay, omitting language in the request, produced an Italian final
segment with speech_language=it, no error_code, 155 audio chunks and verified empty/terminal Stop.
Aggregate-only evidence: runtime/exports/italian-default-http.json. No native inputs were used.
