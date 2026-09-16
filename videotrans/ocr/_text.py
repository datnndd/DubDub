"""Text normalization, similarity, line ordering, and consensus helpers.

Pure stdlib (re, difflib). No heavy dependency imports. The normalization path
here produces a COMPARISON key only; display text must be preserved separately
by callers.
"""
import re
from difflib import SequenceMatcher
from typing import List

# Characters treated as leading/trailing punctuation / common OCR noise.
# Kept broad but conservative; interior word characters are never stripped.
_EDGE_PUNCT = " \t\r\n\"'`~!@#$%^&*()_+\\-=\\[\\]{};:,.<>/?|，。！？、：；「」『』（）《》【】…—·"
_EDGE_PATTERN = re.compile(r"^[%s]+|[%s]+$" % (_EDGE_PUNCT, _EDGE_PUNCT))
_WS_PATTERN = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Return a normalized COMPARISON key for the given text.

    Steps: strip, collapse internal whitespace to single spaces, remove
    leading/trailing punctuation / common OCR noise, and casefold. This value
    is intended for comparison/grouping only and MUST NOT be shown to the user
    as display text.
    """
    if not text:
        return ""
    s = str(text).strip()
    # Collapse internal whitespace to single spaces.
    s = _WS_PATTERN.sub(" ", s)
    # Remove leading/trailing punctuation and OCR noise.
    s = _EDGE_PATTERN.sub("", s)
    # Collapse again in case edge removal exposed spaces, then casefold.
    s = _WS_PATTERN.sub(" ", s).strip()
    return s.casefold()


def text_similarity(a: str, b: str) -> float:
    """Return a 0..1 similarity ratio over normalized text.

    Two empties => 1.0; exactly one empty => 0.0.
    """
    na = normalize_text(a)
    nb = normalize_text(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()


def _box_key(line):
    """Return a (y, x) sort key from an OcrLine-like object, tolerating gaps.

    Missing/invalid boxes sort as if positioned at the very top-left so that
    ordering stays stable for entries without geometry.
    """
    box = None
    if hasattr(line, "box"):
        box = getattr(line, "box")
    elif isinstance(line, dict):
        box = line.get("box")
    if box is None:
        return (0.0, 0.0)
    try:
        x = box[0]
        y = box[1]
    except (TypeError, IndexError, KeyError):
        return (0.0, 0.0)
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return (0.0, 0.0)
    return (float(y), float(x))


def order_lines(lines: List) -> List:
    """Sort OcrLine list top-to-bottom then left-to-right by box (y then x).

    Uses a stable sort so lines without boxes keep their relative order.
    """
    if not lines:
        return list(lines) if lines is not None else []
    return sorted(lines, key=_box_key)


def _obs_text_conf(obs):
    """Extract (text, confidence) from an observation tuple/list/mapping."""
    if isinstance(obs, dict):
        return obs.get("text", ""), float(obs.get("confidence", 0.0) or 0.0)
    text = obs[0]
    conf = 0.0
    if len(obs) > 1 and obs[1] is not None:
        conf = float(obs[1])
    return text, conf


def representative_text(observations: List) -> str:
    """Pick the best-agreement/confidence text from (text, confidence) obs.

    Group observations by normalized comparison key. Choose the group with the
    highest cumulative confidence, breaking ties by group size (count), then by
    the highest single-observation confidence. Within the chosen group, return
    the raw text of the highest-confidence observation.
    """
    if not observations:
        return ""

    groups = {}  # norm_key -> {"sum": float, "count": int, "best": (conf, text)}
    for obs in observations:
        text, conf = _obs_text_conf(obs)
        key = normalize_text(text)
        if key == "":
            # Skip empty observations for representative selection.
            continue
        g = groups.get(key)
        if g is None:
            groups[key] = {"sum": conf, "count": 1, "best": (conf, text)}
        else:
            g["sum"] += conf
            g["count"] += 1
            if conf >= g["best"][0]:
                g["best"] = (conf, text)

    if not groups:
        return ""

    # Rank groups: cumulative confidence, then count, then best single conf.
    best_key = None
    best_rank = None
    for key, g in groups.items():
        rank = (g["sum"], g["count"], g["best"][0])
        if best_rank is None or rank > best_rank:
            best_rank = rank
            best_key = key
    return groups[best_key]["best"][1]
