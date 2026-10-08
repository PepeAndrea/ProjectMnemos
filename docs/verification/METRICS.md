# MVP measurement contract

Measurements record provider/version, fixture hash, hardware/OS, modality, sample count,
mean and p50/p95 latency, cold-load time, peak resident memory and failure count.
Report ingest/process FPS, drops and queue depths independently. Identity benchmarks require
same-instance positives and lookalike negatives; report precision, recall and false identity rate.
ASR reports word error rate by IT/EN, diarization error rate and timestamp deviation.
Retrieval reports recall@k and evidence grounding. Interrupt evaluation records useful/total,
duplicate notifications, cooldown suppression and missed eligible reminders.
Storage growth is bytes/category/day; cloud telemetry records calls, tokens, estimated cost/day
and percent local inference. Raw media, private text and biometrics are never metric labels.

Provisional engineering budgets: overlay p95 <500ms, latest-media queue <=4, audio buffer
<=32MiB, video buffer <=64MiB, duration <=300s. Failure behavior: drop stale frames rather
than grow queues; return unavailable rather than fake model results; never promote semantic
similarity to instance identity. Accuracy thresholds require representative datasets and are
not established by synthetic replay. No milestone passes on synthetic fixture metrics alone.

Run `python -m mnemos.replay` for the foundation harness; output under runtime/exports.
