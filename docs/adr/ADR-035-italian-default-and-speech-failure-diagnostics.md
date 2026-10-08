# ADR-035 — Italian defaults and bounded speech failure diagnostics

Accepted 2026-10-09. User reports audio failure and English output despite the agreed Italian
default. The development core reported `local speech processing unavailable`, 3988 normalized
audio chunks, 310 processed video frames and three audio discontinuities. No exception subtype
was retained. This establishes processing failure after acquisition, not its precise cause.
Do not infer a microphone permission failure or claim that the original cause is resolved.

Italian is now the API, capture factory, streaming speech and ASR default. The dashboard sends
`it` explicitly. Speech replay selects a regenerated Italian stream by default; explicit `en`
continues to use the English regression fixture. No automatic translation is introduced.

An unsupported auto-detected language previously raised and shut down the whole capture.
Now it returns no text for that segment (retracting any partial), increments an aggregate
counter, and allows subsequent supported segments. This is a proven failure path; it is not
proof that it caused the user's particular failure. Native nonzero ASR results and malformed
outputs carry static `speech-asr-failed` / `speech-output-invalid` codes. VAD output failures
carry `speech-vad-failed`; unexpected worker errors use `speech-processing-failed`. Raw driver
errors, audio and transcript text are never logged. Stop still cancels and clears buffers.

Validation: default-language contracts, explicit-English replay regression, unsupported-to-
supported provider recovery, static-error sanitization and real native cancellation tests.
Full suite: 168 passed, zero skips; Ruff/format/mypy and web build pass. Live acquisition must
be retried from the owner's sensor controls: synthetic replay cannot close T013 or establish
that a device/driver/OS issue is fixed. Core restarted only after no active worker was confirmed;
no native sensors were opened by this verification.
