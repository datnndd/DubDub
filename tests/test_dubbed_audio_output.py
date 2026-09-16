from pathlib import Path
from types import SimpleNamespace

from videotrans.configure.config import app_cfg
from videotrans.task._stage_assemble import AssembleMixin
from videotrans.task._stage_prepare import PrepareMixin


class _DubbedAudioTask(AssembleMixin):
    def __init__(self, tmp_path):
        self.cfg = SimpleNamespace(
            app_mode='biaozhun',
            only_out_mp4=False,
            only_out_dubbed_audio=True,
            video_autorate=False,
            source_sub=tmp_path / 'source.srt',
            target_sub=tmp_path / 'target.srt',
            target_wav=tmp_path / 'target.wav',
            source_wav_output=tmp_path / 'source.m4a',
            target_wav_output=tmp_path / 'target.m4a',
            target_dir=tmp_path,
            target_language_code='vi',
            targetdir_mp4=tmp_path / 'result.mp4',
            novoice_mp4=tmp_path / 'cache' / 'novoice.mp4',
            name='input.mp4',
        )
        self.is_audio_trans = False
        self.should_hebing = True
        self.precent = 0
        self.cost_duration = 0
        self.join_called = False
        self.done = False

    def _exit(self):
        return False

    def _join_video_audio_srt(self):
        self.join_called = True

    def set_end(self, success):
        self.done = success

    def signal(self, **_kwargs):
        return None


class _DubbedAudioPrepareTask(PrepareMixin):
    def __init__(self, tmp_path):
        self.uuid = 'only-dubbed-audio'
        self.cfg = SimpleNamespace(
            app_mode='biaozhun',
            only_out_dubbed_audio=True,
            video_autorate=False,
            cache_folder=tmp_path / 'cache',
            target_dir=tmp_path / 'output',
            source_sub=tmp_path / 'output' / 'source.srt',
            target_sub=tmp_path / 'output' / 'target.srt',
            targetdir_mp4=tmp_path / 'output' / 'result.mp4',
            source_wav=tmp_path / 'cache' / 'source.wav',
            vocal=tmp_path / 'cache' / 'vocal.wav',
            instrument=tmp_path / 'cache' / 'instrument.wav',
            is_separate=False,
            name='input.mp4',
        )
        self.is_audio_trans = False
        self.is_copy_video = False
        self.should_recogn = True
        self.should_separate = False
        self.clone_ref = ''

    def _exit(self):
        return False

    def _unlink_size0(self, _paths):
        return None

    def signal(self, **_kwargs):
        return None


def test_dubbed_audio_only_skips_video_assembly(tmp_path):
    task = _DubbedAudioTask(tmp_path)

    task.assembling()

    assert task.join_called is False


def test_dubbed_audio_only_keeps_final_wav_and_removes_other_outputs(tmp_path):
    task = _DubbedAudioTask(tmp_path)
    task.cfg.source_sub.write_text('source subtitle', encoding='utf-8')
    task.cfg.target_sub.write_text('translated subtitle', encoding='utf-8')
    task.cfg.target_wav.write_bytes(b'dubbed audio')
    task.cfg.source_wav_output.write_bytes(b'source audio')
    task.cfg.target_wav_output.write_bytes(b'target audio')
    task.cfg.targetdir_mp4.write_bytes(b'video')
    (Path(task.cfg.target_dir) / 'vocal.wav').write_bytes(b'vocal')
    (Path(task.cfg.target_dir) / 'instrument.wav').write_bytes(b'instrument')

    task.task_done()

    assert (Path(task.cfg.target_dir) / 'vi-dubbing.wav').read_bytes() == b'dubbed audio'
    assert not task.cfg.source_sub.exists()
    assert not task.cfg.target_sub.exists()
    assert not task.cfg.source_wav_output.exists()
    assert not task.cfg.target_wav_output.exists()
    assert not task.cfg.targetdir_mp4.exists()
    assert not (Path(task.cfg.target_dir) / 'vocal.wav').exists()
    assert not (Path(task.cfg.target_dir) / 'instrument.wav').exists()
    assert task.done is True


def test_dubbed_audio_only_exports_slowed_video_without_merging_tts(tmp_path):
    task = _DubbedAudioTask(tmp_path)
    task.cfg.video_autorate = True
    task.cfg.target_wav.write_bytes(b'dubbed audio')
    task.cfg.novoice_mp4.parent.mkdir()
    task.cfg.novoice_mp4.write_bytes(b'slow silent video')

    task.assembling()
    task.task_done()

    assert task.join_called is False
    assert (Path(task.cfg.target_dir) / 'vi-dubbing.wav').read_bytes() == b'dubbed audio'
    assert (Path(task.cfg.target_dir) / 'vi-slowed.mp4').read_bytes() == b'slow silent video'


def test_dubbed_audio_only_skips_video_preparation(monkeypatch, tmp_path):
    from videotrans.task import _stage_prepare

    task = _DubbedAudioPrepareTask(tmp_path)
    task.cfg.target_dir.mkdir()
    task.cfg.source_sub.write_text('source subtitle', encoding='utf-8')
    scheduled_functions = []
    monkeypatch.setattr(
        _stage_prepare,
        'get_video_info',
        lambda _name: {
            'time': 0,
            'streams_audio': 0,
            'video_streams': 1,
            'video_codec_name': 'h264',
            'color': 'yuv420p',
        },
    )
    monkeypatch.setattr(
        _stage_prepare,
        'run_in_threadpool',
        lambda function: scheduled_functions.append(function),
    )

    task.prepare()

    assert scheduled_functions == []
    assert app_cfg.queue_novice[task.uuid] == 'end'


def test_dubbed_audio_only_prepares_video_when_slow_video_is_enabled(monkeypatch, tmp_path):
    from videotrans.task import _stage_prepare

    task = _DubbedAudioPrepareTask(tmp_path)
    task.cfg.video_autorate = True
    task.cfg.target_dir.mkdir()
    task.cfg.source_sub.write_text('source subtitle', encoding='utf-8')
    scheduled_functions = []
    monkeypatch.setattr(
        _stage_prepare,
        'get_video_info',
        lambda _name: {
            'time': 0,
            'streams_audio': 0,
            'video_streams': 1,
            'video_codec_name': 'h264',
            'color': 'yuv420p',
        },
    )
    monkeypatch.setattr(
        _stage_prepare,
        'run_in_threadpool',
        lambda function: scheduled_functions.append(function),
    )

    task.prepare()

    assert scheduled_functions == [task._split_novoice_byraw]
    assert app_cfg.queue_novice[task.uuid] == 'ing'
