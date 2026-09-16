"""Convert OCR segments to the existing SrtItem SRT contract."""
from typing import List

from videotrans.task.taskcfg import SrtItem
from videotrans.util._srt_parse import ms_to_time_string


def segments_to_srt_items(segments: list) -> List[SrtItem]:
    """Convert a list of OcrSegment to a list of SrtItem.

    - line is 1-based and sequential for non-empty segments.
    - start_time / end_time are ints (ms).
    - startraw / endraw use ms_to_time_string -> "HH:MM:SS,mmm".
    - time is "startraw --> endraw".
    - text is the segment text.
    - Empty-text segments are skipped.
    """
    items: List[SrtItem] = []
    if not segments:
        return items
    for seg in segments:
        text = (seg.get("text") if hasattr(seg, "get") else seg["text"]) or ""
        if not str(text).strip():
            continue
        start_ms = int(seg["start_ms"])
        end_ms = int(seg["end_ms"])
        startraw = ms_to_time_string(ms=start_ms)
        endraw = ms_to_time_string(ms=end_ms)
        item = SrtItem(
            line=len(items) + 1,
            start_time=start_ms,
            end_time=end_ms,
            startraw=startraw,
            endraw=endraw,
            time=f"{startraw} --> {endraw}",
            text=text,
        )
        items.append(item)
    return items
