# ADR-021 — Pinned local speech providers

Status: Accepted for reversible baseline implementation, 2026-10-08.

Use whisper.cpp v1.9.5, verified tag/commit d1be6fde11ac6e0407606b4e42fe72d34add8037,
with a narrow project-owned C ABI rather than mirroring the large unstable params struct through
ctypes. Sources, build and models remain under runtime; archive/peso/native artifact SHA gates
prevent silent revision changes. Both code and model-card licenses are permissive MIT.
Primary sources: [whisper.cpp](https://github.com/ggml-org/whisper.cpp/tree/v1.9.5),
[Whisper weights](https://huggingface.co/ggerganov/whisper.cpp/blob/5359861c739e955e79d9a303bcbc70fb988958b1/README.md),
[Silero conversion](https://huggingface.co/ggml-org/whisper-vad/blob/9ffd54a1e1ee413ddf265af9913beaf518d1639b/README.md).

VAD consumes 512-sample/32ms frames with recurrent state preserved; segmentation has 224ms
pre-roll, 480ms endpoint silence, conservative hysteresis and <=15s segment cap. Gaps or source
changes discard unfinished media and reset recurrent/speaker-session state. Partials are refreshed
no faster than 700ms after one second of voiced context and final updates share the utterance ID.
Whisper produces relative timestamps and mean token probability, a decoding proxy which is not
calibrated identity/command confidence. Native transcript logging is disabled; PCM stays in memory.
Speakers remain anonymous. No action authority derives from being transcribed.

M1/8GB comparison on two local synthetic phrases, four runs/model/backend: Tiny Metal warm
p95 ~105ms IT/~80ms EN; Base Metal ~177ms/~165ms; Tiny CPU ~152ms/~174ms and Base CPU
~432ms/~392ms. Silero warm p95 ~0.190ms/32ms frame. Process peak RSS ~362MiB across the
sequential comparison. First context/shader warm-up is variable and can be seconds; capture
integration must prepare or expose warm-up without accumulating unlimited source backlog.

All four ASR choices had WER 2/7 IT and 2/6 EN on this tiny synthetic set, including Tobi/name
errors. Base did not improve this measured fixture; choose Tiny Metal provisionally for stream
latency, keeping Base selectable. This is not representative accuracy and cannot authorize real
voice enrollment. Do not hide errors or normalize benchmark transcripts to improve scores.
Further real/consented acoustic calibration and language-specific evaluation remain required.

Real streaming replay, endpoint/silence, partial/final revision, discontinuity, invalid input,
model eviction and WER computation tests pass. Live microphone verification and representative calibration remain outstanding; T014/T015 are not declared Done.

Continuous integration decision: prepare VAD/ASR before opening sources, then reset the common
clock. Process speech on one worker behind a 128-chunk queue (2.56s at standard 20ms chunks).
Drop oldest audio on overload and expose discontinuities; discard incomplete partials across a
gap. Keep at most 50 utterance revisions for <=300s, entirely volatile. Stop/failure/EOF clears
text, media and queues. Cancellation is sticky for the current native context, preventing a
stop/run race; reuse requires unload/new context. Real cancellation and live HTTP replay verify
this behavior. The dashboard explicitly reports warm-up and temporary anonymous transcripts.

Audio/video EOF must be independent: each consumer drains/flushes its own source queue rather
than waiting for all producers. Speech EOF releases VAD/ASR and clears rolling PCM even when
video continues. A regression test covers asymmetric source durations.
