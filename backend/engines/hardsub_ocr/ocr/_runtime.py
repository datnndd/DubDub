"""Bridge streamed ROI images and the shared scanner to sidecar cue JSON."""
from ._frame_source import probe, sampled_frame_iter
from ._providers import EngineProvider
from ._scanner import OcrScanner
from ._types import OcrConfig
from ._checkpoint import video_fingerprint


def buffered_coarse_iter(frames, stride, window):
    """Yield coarse frames while retaining only their preceding fine window."""
    pending = []
    for index, timestamp, image in frames:
        if index % stride:
            pending.append((round(timestamp * 1000), image))
            continue
        window[:] = pending
        yield index // stride, timestamp, image
        pending = []


def _normalize_ranges(ranges, min_gap=0.5):
    if not ranges:
        return []
    cleaned = []
    for r in ranges:
        if len(r) >= 2:
            s, e = float(r[0]), float(r[1])
            if e > s:
                cleaned.append((max(0.0, s), max(0.0, e)))
    cleaned.sort(key=lambda x: x[0])
    if not cleaned:
        return []
    merged = [cleaned[0]]
    for cur_s, cur_e in cleaned[1:]:
        prev_s, prev_e = merged[-1]
        if cur_s <= prev_e + min_gap:
            merged[-1] = (prev_s, max(prev_e, cur_e))
        else:
            merged.append((cur_s, cur_e))
    return merged


def scan_video(video, crop, engine, *, fps=2.0, threshold=0.5, on_progress=None,
               checkpoint_path=None, model_identity=None, refine=False, refine_fps=6.0,
               time_ranges=None):
    _, _, duration = probe(video)
    norm_ranges = _normalize_ranges(time_ranges) if time_ranges else None
    if norm_ranges:
        all_cues = []
        for r_start, r_end in norm_ranges:
            r_start = min(duration, max(0.0, r_start))
            r_end = min(duration, max(r_start, r_end))
            if r_end <= r_start:
                continue
            config = OcrConfig(roi=(0, 0, 1, 1), coarse_interval_ms=round(1000 / fps))
            config.fingerprint = video_fingerprint(video, round(duration * 1000))
            config.source_crop = dict(crop)
            config.frame_sampling = 'ffmpeg-fps-round-up-v1'
            config.text_score = threshold
            config.model_identity = model_identity
            config.refine_enabled = False
            scanner = OcrScanner(EngineProvider(engine, threshold), config, on_progress=on_progress,
                                 checkpoint_path=None)
            raw_source = sampled_frame_iter(video, crop, fps, window_start=r_start, window_end=r_end)
            try:
                segments = scanner.scan(((round(ts * 1000), image) for _, ts, image in raw_source),
                                        duration_ms=round(r_end * 1000), resume=False)
            finally:
                raw_source.close()
            for index, segment in enumerate(segments):
                if not segment.text:
                    continue
                next_start = segments[index + 1].start_ms / 1000 if index + 1 < len(segments) else r_end
                c_start = max(r_start, round(segment.start_ms / 1000, 3))
                c_end = min(r_end, round(min(next_start, segment.end_ms / 1000 + 1 / fps), 3))
                if c_end > c_start and segment.text.strip():
                    all_cues.append(dict(start=c_start, end=c_end, text=segment.text.strip()))
        all_cues.sort(key=lambda c: c["start"])
        return all_cues
    config = OcrConfig(roi=(0, 0, 1, 1), coarse_interval_ms=round(1000 / fps))
    config.fingerprint = video_fingerprint(video, round(duration * 1000))
    config.source_crop = dict(crop)
    config.frame_sampling = 'ffmpeg-fps-round-up-v1'
    config.text_score = threshold
    config.model_identity = model_identity
    config.refine_enabled = refine
    refinement_window = []
    source_fps = fps
    stride = 1
    if refine:
        config.boundary_interval_ms = max(1, round(1000 / refine_fps))
        ratio = refine_fps / fps
        stride = round(ratio)
        if stride >= 2 and abs(ratio - stride) < 1e-9:
            source_fps = refine_fps

            def frames_between(start, end, step):
                yield from ((ts, image) for ts, image in refinement_window if start < ts < end)
        else:
            def frames_between(start, end, step):
                local_source = sampled_frame_iter(
                    video, crop, 1000 / step,
                    window_start=(start + step) / 1000, window_end=end / 1000,
                )
                try:
                    for _, ts, image in local_source:
                        yield round(ts * 1000), image
                finally:
                    local_source.close()
        config.frames_between = frames_between
    scanner = OcrScanner(EngineProvider(engine, threshold), config, on_progress=on_progress,
                         checkpoint_path=checkpoint_path)
    start_coarse_index = 0
    checkpoint = scanner._maybe_load_checkpoint(True)
    if checkpoint is not None:
        start_coarse_index = max(0, checkpoint.last_processed_ms // config.coarse_interval_ms + 1)
    raw_source = sampled_frame_iter(video, crop, source_fps,
                                    start_index=start_coarse_index * stride)
    source = buffered_coarse_iter(raw_source, stride, refinement_window) if stride > 1 else raw_source
    try:
        segments = scanner.scan(((round(ts * 1000), image) for _, ts, image in source),
                                duration_ms=round(duration * 1000), resume=True)
    finally:
        source.close()
        if source is not raw_source:
            raw_source.close()
    segments = [segment for segment in segments if segment.text]
    cues = []
    for index, segment in enumerate(segments):
        # Last observed samples cover one interval, but a direct transition
        # already ends at the next cue's start. Never extend across that start.
        next_start = segments[index + 1].start_ms / 1000 if index + 1 < len(segments) else duration
        cues.append(dict(start=segment.start_ms / 1000,
                         end=min(duration, next_start, segment.end_ms / 1000 + 1 / fps),
                         text=segment.text))
    return cues
