# 0001 Video OCR As A Subtitle Source

Date: 2026-08-12

## Status

Accepted

## Context

pyVideoTrans currently produces source subtitles through audio speech
recognition and then uses an SRT file as the boundary for editing, translation,
dubbing, alignment, and assembly. The new feature must recognize burned-in
subtitles inside a user-selected fixed video region, preserve timestamps, and
reuse those later stages. The first release targets one 30-120 minute video at a
time and must support preview, checkpoint, and resume.

## Decision

Implement hard-subtitle OCR as a selectable recognition source inside the
existing video-translation pipeline. It must write the normal `source_sub` SRT
and return control to the existing single-video subtitle editing flow.

Keep OCR inference behind a provider boundary, with PaddleOCR as the first local
provider. Scan and crop ROI frames in memory; do not physically split or
re-encode the video into scenes. Use adaptive sampling, selective OCR, text
similarity, and local boundary refinement rather than OCR on every video frame.

## Alternatives Considered

1. A standalone OCR-to-SRT utility followed by manually importing the SRT.
   This isolates implementation but creates a fragmented user experience and
   separates checkpoint/progress from the main task.
2. A new OCR stage and worker queue parallel to the existing pipeline stages.
   This could suit future batch scaling but adds routing and lifecycle
   complexity that the single-video MVP does not require.
3. Physically split the video into detected scenes before OCR and translation.
   This adds temporary storage and avoidable decode/encode I/O without improving
   the SRT integration boundary.

## Consequences

Positive:

- Existing SRT editing, translation, dubbing, alignment, and assembly behavior
  is reused.
- Audio ASR remains unchanged and can stay the default subtitle source.
- A future online OCR provider can be added without coupling it to video scan
  and segment-building logic.
- Avoiding physical scene clips reduces temporary storage and encoding work.

Tradeoffs:

- Recognition routing and task configuration must distinguish audio ASR from
  video OCR.
- The desktop task cannot begin until a valid ROI has been previewed and
  confirmed.
- PaddleOCR/PaddlePaddle remains an optional dependency with a platform and GPU
  compatibility surface that needs explicit validation.
- Adaptive timestamp construction is more involved than emitting OCR results at
  a fixed interval, but is required to avoid fragmented subtitles and meet the
  accepted 250 ms tolerance.

## Follow-Up

- Execute `docs/plans/active/video-ocr-subtitles.md`.
- Revisit a dedicated OCR worker or batch workflow only when multiple-video OCR
  becomes an accepted product requirement.
- Revisit the provider set when an online OCR implementation is explicitly
  selected for delivery.

