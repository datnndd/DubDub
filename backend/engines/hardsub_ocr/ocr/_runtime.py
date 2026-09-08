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


def scan_video(video, crop, engine, *, fps=2.0, threshold=0.5, on_progress=None,
               checkpoint_path=None, model_identity=None, refine=False, refine_fps=6.0):
    _, _, duration = probe(video)
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
