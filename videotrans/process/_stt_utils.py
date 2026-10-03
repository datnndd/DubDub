import json, re
from typing import List
from videotrans.task.taskcfg import SrtItem

from ._utils import _write_log


def _remove_unwanted_characters(text: str) -> str:
    # Retain Chinese, Japanese, Korean, English, numbers, and common symbols, remove other characters
    allowed_characters = re.compile(r'<\|\w+\|>')
    return re.sub(allowed_characters, '', text)


def _resegment(texts, language, max_speech_ms, logs_file=None) -> List[SrtItem]:
    """
    Only re-segment overlong Whisper recognition results and format as SRT subtitles.
    Preserves Whisper's originally normal short sentences without flattening globally.
    """

    # --- Helper function: convert milliseconds to SRT standard time format HH:MM:SS,mmm ---
    def format_srt_time(ms_time):
        ms_time = int(ms_time)
        seconds, milliseconds = divmod(ms_time, 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    # --- Language concatenation rules and punctuation determination ---
    # CJK and certain Asian languages do not need spaces; alphabetic languages do
    no_space_langs = {'zh', 'ja', 'th', 'yue', 'ko', 'km'}
    use_space = language.lower() not in no_space_langs

    end_punc = set('.?!。？！\n')
    comma_punc = set(',;:，；：、')

    def has_punc(text, punc_set):
        if not text:
            return False
        return text[-1] in punc_set

    def build_text(chunk_words):
        if use_space:
            text_str = " ".join(chunk_words)
            # Fix leading space before punctuation caused by space-joining in alphabetic languages (e.g. "Hello , world" -> "Hello, world")
            text_str = re.sub(r'\s+([.,?!:;])', r'\1', text_str)
        else:
            text_str = "".join(chunk_words)
        return text_str.strip()

    # --- Core logic ---
    final_segments = []

    _len = len(texts)
    _block = 100 / _len
    for seg_idx, segment in enumerate(texts):
        seg_start_ms = float(segment.get('start', 0)) * 1000
        seg_end_ms = float(segment.get('end', 0)) * 1000
        seg_duration = seg_end_ms - seg_start_ms
        words = segment.get('words', [])
        _c_percent = seg_idx * _block
        _write_log(logs_file, json.dumps({"type": "logs", "text": f'Resegment:{_c_percent:.2f}%'}))

        # 1. If this sentence does not exceed max_speech_ms, or has no words data for subdivision
        # Preserve original sentence directly without breaking Whisper's original segmentation structure
        if seg_duration <= max_speech_ms or not words:
            final_segments.append({
                'text': segment.get('text', '').strip(),
                'start': seg_start_ms,
                'end': seg_end_ms
            })
            continue

        # 2. If this sentence is overlong, recursively subdivide internally using word-level timestamps
        current_chunk = []
        chunk_start_ms = None
        prev_word_end_ms = None
        prev_word_text = ""

        for w_idx, w in enumerate(words):
            _c_percent += w_idx * (_block / len(words))
            _write_log(logs_file, json.dumps({"type": "logs", "text": f'Resegment:{_c_percent:.2f}%'}))
            w_text = w.get('word', '').strip()
            if not w_text:
                continue

            w_start_ms = float(w.get('start', 0)) * 1000
            w_end_ms = float(w.get('end', 0)) * 1000

            if chunk_start_ms is None:
                chunk_start_ms = w_start_ms

            # Look ahead: what would the chunk duration be if this word is added?
            future_duration = w_end_ms - chunk_start_ms

            # --- Determine if split is needed ---
            should_split = False

            # Hard split: adding this word exceeds max_speech_ms (guarantees strictly <= max_speech_ms)
            if future_duration > max_speech_ms and len(current_chunk) > 0:
                should_split = True
            else:
                # Soft split: find punctuation or obvious speech pause while remaining within duration limits
                pause_ms = w_start_ms - prev_word_end_ms if prev_word_end_ms is not None else 0
                current_duration = prev_word_end_ms - chunk_start_ms if prev_word_end_ms else 0

                if len(current_chunk) > 0:
                    # Strong sentence-ending punctuation reached
                    if has_punc(prev_word_text, end_punc):
                        should_split = True
                    # Obvious long silence pause reached (>= 800ms)
                    elif pause_ms >= 800:
                        should_split = True
                    # Short pause (>= 300ms) with weak punctuation like comma
                    elif has_punc(prev_word_text, comma_punc) and pause_ms >= 300:
                        should_split = True
                    # For long sentences without punctuation or major pauses, split if elapsed duration > 50% and pause >= 400ms
                    elif current_duration > (max_speech_ms * 0.5) and pause_ms >= 400:
                        should_split = True

            if should_split:
                # Commit current chunk
                final_segments.append({
                    'text': build_text(current_chunk),
                    'start': chunk_start_ms,
                    'end': prev_word_end_ms
                })
                # Start new chunk with current word
                current_chunk = [w_text]
                chunk_start_ms = w_start_ms
            else:
                # Do not split, append word to current chunk
                current_chunk.append(w_text)

            prev_word_end_ms = w_end_ms
            prev_word_text = w_text

        # After iterating all words, flush remaining chunk
        if current_chunk:
            final_segments.append({
                'text': build_text(current_chunk),
                'start': chunk_start_ms,
                'end': prev_word_end_ms
            })

    # --- 3. Assemble output: wrap into list of SrtItem objects ---
    srt_output = []
    for idx, seg in enumerate(final_segments):
        start_ms = int(seg['start'])
        end_ms = int(seg['end'])

        start_raw = format_srt_time(start_ms)
        end_raw = format_srt_time(end_ms)

        srt_output.append(SrtItem(**{
            "line": idx + 1,
            "text": seg['text'],
            "start_time": start_ms,
            "end_time": end_ms,
            "startraw": start_raw,
            "endraw": end_raw,
            "time": f"{start_raw} --> {end_raw}"
        }))
    _write_log(logs_file, json.dumps({"type": "logs", "text": f'Resegment:ended'}))
    return srt_output
