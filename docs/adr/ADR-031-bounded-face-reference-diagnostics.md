# ADR-031 — Bounded face reference diagnostics

Accepted 2026-10-08; partial T018, prepares T012/T020. No calibrated biometric quality claim.

Preserve YuNet's five-point output in bounded session-local detector/tracker state. Public
capture detections, tracks and events omit raw points. Only explicit consent-bound acquisition
(ADR-030) uses current selected geometry. Track loss, stale-frame expiry and Stop/failure clear
its acquisition map. No persistent unknown identity added.

Share one grayscale area-resampled image (longest side 256px) with ADR-029 diagnostics.
Measure Laplacian variance, eye span/nose projection and eye-line roll. Sort eyes by screen
position. Original coordinates determine geometry even when the JPEG is resized. Store only
derived metrics in consent-bound reference quality; no raw points in reference/audit payloads.

Missing geometry is explicitly unassessed. Malformed/nonfinite points reject acquisition.
Warnings: detail variance <25, eye-line tilt >20 degrees, eye span <0.15 box width, asymmetric
nose projection >0.35 eye span, degeneracy or points outside crop. These provisional thresholds
neither certify sharpness nor estimate calibrated 3D yaw/pitch, identity, emotion or demographics.
Keep usable images with warnings: profile views must not be forbidden by a frontal proxy.

Spike: full-resolution Laplacian vs bounded total diagnostics on six generated patterns/point
sets (50 repeats). Full-only p95 ~4.9ms; bounded total ~16.3ms at 1600px and ~0.16ms at 128px.
Bounded is slower for large images due to area resampling, but derivative arrays have at most
65,536 instead of 2,560,000 pixels. This episodic owner-request path accepts that cost; do not
run it on every frame. An initially duplicated resample was removed after measurement.
No new model/runtime or microservice is justified. Concurrent test/model runs raised the large-case p95 to 23–31ms; final report was repeated after those processes finished.

One wholly AI-generated portrait, hash/prompt pinned under runtime/datasets/face-synthetic,
exercises real pinned YuNet, tracking and cropping. This is a positive plumbing regression,
not a representative dataset or consented field evaluation. Output schema source:
[OpenCV tutorial](https://docs.opencv.org/4.13.0/d0/dd4/tutorial_dnn_face.html).

Remaining T018: real authorized acquisition, pose/view diversity criteria and representative
quality acceptance. Alignment/matching and identity accuracy remain T020. No Done claim.
