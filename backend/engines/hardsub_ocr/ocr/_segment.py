"""Subtitle segment builder state machine.

Implements EMPTY -> CANDIDATE -> ACTIVE -> CHANGING -> EMPTY/ACTIVE with:

- min_stable_samples similar samples OR a single strong observation to open.
- similarity-based merging so minor OCR variation does not fragment.
- grace-gap bridging of short empty runs (fade in/out).
- direct text-change handling: close previous at the transition timestamp and
  open the next there.
- identical text separated by a clear empty gap (> grace_gap_ms) stays as two
  distinct segments.
- representative text chosen via consensus across the segment's observations.

Memory is bounded: only the observations of the current candidate/active
segment are retained, never the whole video.

Pure stdlib; no heavy imports.
"""
from typing import List

from ._types import OcrConfig, OcrResult, OcrSegment
from ._text import normalize_text, text_similarity, representative_text


# Internal states
_EMPTY = "EMPTY"
_ACTIVE = "ACTIVE"


class SegmentBuilder:
    """Consolidate sampled OCR observations into stable subtitle segments."""

    def __init__(self, config: OcrConfig):
        self.config = config or OcrConfig()
        self._segments = []  # completed OcrSegment list

        self._state = _EMPTY
        # Buffered observations for the not-yet-confirmed candidate.
        # Each entry: {"ts": int, "text": str, "confidence": float}
        self._cand = []
        # Confirmed/open segment tracking.
        self._open = None  # dict or None while a segment is open/active
        # Timestamp of the start of the current empty gap while active.
        self._gap_start_ms = None
        # Timestamp of the most recent non-empty (active) observation.
        self._last_active_ts = None

    # -- helpers ---------------------------------------------------------
    @property
    def _strong_threshold(self) -> float:
        # A "strong" single observation is confident enough to open a segment
        # without waiting for min_stable_samples.
        return 0.90

    def _is_similar(self, a: str, b: str) -> bool:
        return text_similarity(a, b) >= self.config.similarity_threshold

    def _open_segment_from_candidate(self):
        """Promote buffered candidate observations to an open ACTIVE segment."""
        obs = self._cand
        start_ms = obs[0]["ts"]
        self._open = {
            "start_ms": start_ms,
            "last_ts": obs[-1]["ts"],
            "observations": [(o["text"], o["confidence"]) for o in obs],
        }
        self._last_active_ts = obs[-1]["ts"]
        self._gap_start_ms = None
        self._state = _ACTIVE
        self._cand = []

    def _finish_open(self, end_ms: int):
        """Close the currently open segment ending at end_ms."""
        if self._open is None:
            return
        obs = self._open["observations"]
        text = representative_text(obs)
        confs = [c for (_t, c) in obs]
        avg_conf = sum(confs) / len(confs) if confs else 0.0
        seg = OcrSegment(
            start_ms=int(self._open["start_ms"]),
            end_ms=int(end_ms),
            text=text,
            confidence=avg_conf,
            samples=len(obs),
        )
        # Only emit segments that carry text.
        if seg.text:
            self._segments.append(seg)
        self._open = None
        self._gap_start_ms = None
        self._last_active_ts = None

    def _reset_candidate_with(self, ts: int, text: str, conf: float):
        self._cand = [{"ts": ts, "text": text, "confidence": conf}]

    # -- public API ------------------------------------------------------
    def observe(self, timestamp_ms: int, result: OcrResult):
        """Feed one sampled observation. Empty text is a normal observation."""
        ts = int(timestamp_ms)
        text = (result.text if result is not None else "") or ""
        conf = float(result.confidence if result is not None else 0.0)
        norm = normalize_text(text)
        is_empty = norm == ""

        if self._state == _EMPTY:
            if is_empty:
                # Still empty; drop any stale candidate.
                self._cand = []
                return
            # Non-empty: accumulate candidate.
            if not self._cand:
                self._reset_candidate_with(ts, text, conf)
            else:
                if self._is_similar(self._cand[-1]["text"], text):
                    self._cand.append({"ts": ts, "text": text, "confidence": conf})
                else:
                    # Different text resets the candidate window.
                    self._reset_candidate_with(ts, text, conf)
            # Open if strong single obs OR enough stable similar samples.
            strong = conf >= self._strong_threshold
            if strong or len(self._cand) >= max(1, self.config.min_stable_samples):
                self._open_segment_from_candidate()
            return

        # state == ACTIVE (a segment is open)
        if is_empty:
            # Begin/continue an empty gap; bridge up to grace_gap_ms.
            if self._gap_start_ms is None:
                self._gap_start_ms = ts
            gap = ts - self._last_active_ts
            if gap > self.config.grace_gap_ms:
                # Close the segment at the last active timestamp.
                self._finish_open(self._last_active_ts)
                self._state = _EMPTY
                self._cand = []
            return

        # Non-empty while active.
        open_rep = representative_text(self._open["observations"])
        last_open_text = self._open["observations"][-1][0]
        if self._is_similar(last_open_text, text) or self._is_similar(open_rep, text):
            # Same subtitle continues (possibly after a bridged short gap).
            self._open["observations"].append((text, conf))
            self._open["last_ts"] = ts
            self._last_active_ts = ts
            self._gap_start_ms = None
            return

        # Different stable text without a clear empty gap => transition.
        # Close previous at this transition timestamp and open next here.
        self._finish_open(ts)
        self._state = _EMPTY
        self._reset_candidate_with(ts, text, conf)
        strong = conf >= self._strong_threshold
        if strong or len(self._cand) >= max(1, self.config.min_stable_samples):
            self._open_segment_from_candidate()

    def snapshot_completed(self) -> List[OcrSegment]:
        """Return completed (closed) segments without closing any open segment.

        Used for periodic checkpointing so an in-progress segment is not
        prematurely finalized.
        """
        return sorted(self._segments, key=lambda s: s.start_ms)
    def finalize(self) -> List[OcrSegment]:
        """Close any open segment and return all segments sorted by start_ms."""
        if self._open is not None:
            end_ms = (
                self._last_active_ts
                if self._last_active_ts is not None
                else self._open["last_ts"]
            )
            self._finish_open(end_ms)
        self._state = _EMPTY
        self._cand = []
        return sorted(self._segments, key=lambda s: s.start_ms)

