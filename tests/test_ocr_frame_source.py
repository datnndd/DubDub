import sys
from pathlib import Path
import subprocess

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from engines.hardsub_ocr.ocr._frame_source import sampled_frame_iter
from engines.hardsub_ocr.ocr._runtime import buffered_coarse_iter


def test_raw_stream_crop_resume_and_close(tmp_path):
    video = tmp_path / 'source.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                    'color=c=white:s=100x100:d=2:r=10', '-y', str(video)], check=True)
    crop = dict(left=0, top=0.8, right=1, bottom=1)
    frames = list(sampled_frame_iter(str(video), crop))
    assert len(frames) == 4
    assert frames[0][2].shape[1:] == (100, 3)
    assert frames[0][2].shape[0] == 20
    resumed = list(sampled_frame_iter(str(video), crop, start_index=2))
    assert [row[0] for row in resumed] == [2, 3]
    assert resumed[0][1] == pytest.approx(1)
    stream = sampled_frame_iter(str(video), crop)
    next(stream)
    stream.close()
    from types import SimpleNamespace
    from engines.hardsub_ocr.ocr._runtime import scan_video
    calls = []
    def engine(image):
        calls.append(image.shape)
        return SimpleNamespace(txts=['sample'], scores=[.99], boxes=None)
    cues = scan_video(str(video), crop, engine)
    assert cues == [dict(start=0, end=2, text='sample')]
    assert len(calls) == 2


def test_runtime_adjacent_cues_never_overlap(monkeypatch):
    from engines.hardsub_ocr.ocr import _runtime
    from engines.hardsub_ocr.ocr._types import OcrSegment

    monkeypatch.setattr(_runtime, 'probe', lambda _: (100, 100, 2.0))
    monkeypatch.setattr(_runtime, 'video_fingerprint', lambda *args: {})
    monkeypatch.setattr(_runtime.OcrScanner, 'scan', lambda *args, **kwargs: [
        OcrSegment(start_ms=0, end_ms=1000, text='first'),
        OcrSegment(start_ms=1000, end_ms=1500, text='second'),
    ])
    # Use a generator so the production finally block can close the stream.
    monkeypatch.setattr(_runtime, 'sampled_frame_iter', lambda *args, **kwargs: (x for x in ()))
    cues = _runtime.scan_video('fixture.mp4', dict(left=0, top=.8, right=1, bottom=1), None)
    assert cues == [dict(start=0, end=1, text='first'), dict(start=1, end=2, text='second')]


def test_runtime_resume_starts_decoder_after_checkpoint(tmp_path, monkeypatch):
    from engines.hardsub_ocr.ocr import _runtime
    from types import SimpleNamespace
    video = tmp_path / 'resume.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                    'color=c=white:s=100x100:d=2:r=10', '-y', str(video)], check=True)
    crop = dict(left=0, top=.8, right=1, bottom=1)
    checkpoint = str(tmp_path / 'resume.json')
    engine = lambda image: SimpleNamespace(txts=['same'], scores=[.99], boxes=None)
    _runtime.scan_video(str(video), crop, engine, checkpoint_path=checkpoint,
                        model_identity='fixture')
    original = _runtime.sampled_frame_iter
    starts = []
    def recording_source(*args, **kwargs):
        starts.append(kwargs.get('start_index', 0))
        return original(*args, **kwargs)
    monkeypatch.setattr(_runtime, 'sampled_frame_iter', recording_source)
    cues = _runtime.scan_video(str(video), crop, engine, checkpoint_path=checkpoint,
                               model_identity='fixture')
    assert starts == [4]
    assert cues == [dict(start=0, end=2, text='same')]


def test_refinement_window_decodes_real_local_frames(tmp_path):
    video = tmp_path / 'transition.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                    'color=c=black:s=100x100:d=0.4:r=20', '-f', 'lavfi', '-i',
                    'color=c=white:s=100x100:d=0.6:r=20', '-filter_complex',
                    '[0:v][1:v]concat=n=2:v=1:a=0', '-y', str(video)], check=True)
    frames = list(sampled_frame_iter(str(video), dict(left=0, top=.8, right=1, bottom=1),
                                    fps=1000/150, window_start=.15, window_end=.5))
    assert [round(ts, 2) for _, ts, _ in frames] == [.15, .3, .45]
    assert frames[0][2].mean() < 10
    assert frames[-1][2].mean() > 240


def test_coarse_sampling_matches_declared_timestamp(tmp_path):
    video = tmp_path / 'early-transition.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                    'color=c=black:s=100x100:d=1:r=20', '-vf',
                    "drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='gte(t,0.1)'",
                    '-y', str(video)], check=True)
    frames = list(sampled_frame_iter(str(video), dict(left=0, top=0, right=1, bottom=1)))
    assert frames[0][1] == 0
    assert frames[0][2].mean() < 10, 'Frame declared at t=0 must precede the t=0.1 transition'
    assert frames[1][1] == .5
    assert frames[1][2].mean() > 240


def test_buffered_fine_stream_keeps_only_previous_coarse_window():
    window = []
    source = buffered_coarse_iter([(i, i / 10, i) for i in range(11)], 5, window)
    assert next(source) == (0, 0, 0)
    assert window == []
    assert next(source) == (1, .5, 5)
    assert window == [(100, 1), (200, 2), (300, 3), (400, 4)]
    assert next(source) == (2, 1, 10)
    assert window == [(600, 6), (700, 7), (800, 8), (900, 9)]
