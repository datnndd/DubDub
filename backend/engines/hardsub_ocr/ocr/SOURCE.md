# Source

The `_types`, `_text`, `_segment`, `_checkpoint`, `_scanner`, `_paddle`, and `_provider_base` modules
are adapted from pyVideoTrans, revision
`c5788f7f342d8ee4f480cf034b85855d09b253ba`, local working-tree snapshot on
2026-09-07. Imports are made relative to this package. Upstream GPLv3 license
is preserved in COPYING. No runtime dependency on the sibling checkout exists.

VoiceStudio adaptations include sequential raw-frame streaming, engine-result
normalization, exact active-state checkpoints, skipped-frame cue coverage,
display-text preservation, progress counters, and non-overlapping cue export.
Local boundary refinement and real-video parity validation remain in progress.
