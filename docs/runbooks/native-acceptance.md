# Bounded native acceptance

Use only after the owner has authorized the specific sensors, with the development core idle.
Dry-run (no device access/network request):

```
runtime/core-venv/bin/python -m mnemos.native_acceptance --camera --microphone
```

Add `--run` only for the authorized live check; choose camera and/or microphone separately.
Duration defaults to five seconds, bounded to 3–30. No transcription or media export is enabled.
The tool refuses existing active sessions and stops only the session it started; it never stops
a replacement session. A missing start response cannot justify stopping an unidentified session:
inspect the owner panel and Stop there if necessary. macOS device prompts require the owner.

Only aggregate counts, static error codes, requested scope and verified cleanup are written to
runtime/exports/native-acceptance.json. Passing requires observed selected normalized inputs,
a valid camera preview in memory if requested, no processing error and empty buffers/terminal
workers after Stop. Fake-call tests verify refusal, replacement, failure and report sanitization.
No live native acceptance has been performed by this tool yet; do not mark T007/T013 Done from
its dry-run or mock tests.
