import datetime
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List
from videotrans import tts
from videotrans.configure.config import tr, settings, app_cfg, logger, HOME_DIR
from videotrans.task._base import BaseTask
from videotrans.task.taskcfg import TaskCfgTTS, SrtItem


"""
Dubbing-only task: corresponds to the "Batch Dubbing for Subtitles" panel.
"""


@dataclass
class DubbingSrt(BaseTask):
    cfg: TaskCfgTTS = field(default_factory=TaskCfgTTS, repr=False)
    out_ext: str = "wav"
    # Whether this is the multi-role subtitle dubbing feature
    is_multi_role: bool = field(init=True, default=False)
    # Fixed to True
    should_dubbing: bool = True
    ignore_align: bool = False
    # Directly use this subtitle info during multi-role dubbing
    subs: List = field(default_factory=list, repr=False)

    def __post_init__(self):
        super().__post_init__()
        # Target output location
        if not self.cfg.target_dir:
            self.cfg.target_dir = f"{HOME_DIR}/tts"
        # Subtitle file requiring dubbing
        self.cfg.target_sub = self.cfg.name
        # Audio file after dubbing saved as
        self.cfg.target_wav = f'{self.cfg.target_dir}/{self.cfg.noextname}.wav'
        self.signal(text=tr("Dubbing from subtitles"))
        logger.debug(f'配音 {self.cfg=}')
        Path(self.cfg.target_dir).mkdir(parents=True, exist_ok=True)
        Path(self.cfg.cache_folder).mkdir(parents=True, exist_ok=True)



    def dubbing(self):
        self.signal(text=Path(self.cfg.target_sub).read_text(encoding='utf-8'), type="replace")
        self._tts()

    def _tts(self) -> None:
        from videotrans.util.help_srt import get_subtitle_from_srt
        queue_tts = []
        # Get subtitles
        try:
            rate = int(str(self.cfg.voice_rate).replace('%', ''))
        except (TypeError,ValueError):
            rate = 0

        rate = f"+{rate}%" if rate >= 0 else f"{rate}%"

        # If the dubbing file is a txt, convert it to single-line subtitle format for unified processing
        if self.cfg.target_sub.endswith('.txt'):
            text = Path(self.cfg.target_sub).read_text(encoding='utf-8').strip()
            text = re.sub(r"(\s*?\r?\n\s*?){2,}", "\n", text, flags=re.I | re.S)
            text = re.sub(r"(\s*?\r?\n\s*?)", "\n", text, flags=re.I | re.S)

            text_list = re.split(r'(\r?\n)+?', text)
            subs = []
            for i, it in enumerate(text_list):
                if not it.strip():
                    continue
                subs.append(SrtItem(
                    line=i + 1,
                    start_time=i * 1000,
                    end_time=i * 1000 + 1000,
                    startraw=f"00:00:00,000",
                    endraw="00:00:01,000",
                    text=it
                ))
        elif self.subs:
            subs = self.subs
        else:
            subs = get_subtitle_from_srt(self.cfg.target_sub)

        # Extract each subtitle: line number\nstart time --> end time\ncontent
        for i, it in enumerate(subs):
            if it['end_time'] < it['start_time'] or not it['text'].strip():
                continue
            try:
                spec_role = app_cfg.dubbing_role.get(int(it.get('line', 1))) if self.is_multi_role else None
            except Exception as e:
                # Individual role for each subtitle, errors can be ignored
                logger.exception(f'每条字幕的单独角色:{e}',exc_info=True)
                spec_role = None
            voice_role = spec_role if spec_role else self.cfg.voice_role
            from videotrans.util.help_misc import get_md5
            _key = get_md5(
                f"{self.cfg.target_language_code}-{it['text']}-{voice_role}-{rate}-{self.cfg.volume}-{self.cfg.pitch}-{self.cfg.tts_type}")
            tmp_dict = {
                "line": it['line'],
                "text": it['text'],
                "role": voice_role,
                "start_time": it['start_time'],
                "end_time": it['end_time'],
                "rate": rate,
                "volume": self.cfg.volume,
                "pitch": self.cfg.pitch,
                "tts_type": int(self.cfg.tts_type),
                "filename": f"{self.cfg.cache_folder}/dubb-{i}-{_key}.wav"}
            queue_tts.append(tmp_dict)

        if not queue_tts or len(queue_tts) < 1:
            from videotrans.configure.excepts import DubbingSrtError
            raise DubbingSrtError(tr('No subtitles required'))
        self.queue_tts = queue_tts

        # Call dubbing channel operations
        tts.run(
            queue_tts=self.queue_tts,
            language=self.cfg.target_language_code,
            uuid=self.uuid,
            tts_type=self.cfg.tts_type,
            is_cuda=self.cfg.is_cuda,
            event_sink=self.event_sink,
            cancellation_token=self.cancellation_token,
        )
        # If individual dubbing audio for each subtitle needs to be saved separately
        if settings.get('save_segment_audio', False):
            outname = self.cfg.target_dir + f'/segment_audio_{self.cfg.noextname}'
            Path(outname).mkdir(parents=True, exist_ok=True)
            for it in self.queue_tts:
                if Path(it['filename']).exists():
                    text = re.sub(r'["\'*?\\/|:<>\r\n\t]+', '', it['text'], flags=re.I | re.S)
                    name = f'{outname}/{it["start_time"]}-{text[:60]}.wav'
                    try:
                        shutil.copy2(it['filename'], name)
                    except shutil.SameFileError:
                        # Ignore same file error
                        pass

    # Audio speedup to align subtitles
    def align(self) -> None:
        if self.ignore_align: return
        from videotrans.util.help_ffmpeg import runffmpeg
        # Only one line
        if len(self.queue_tts) < 2:
            if len(self.queue_tts) == 1:
                runffmpeg(['-y', '-i', self.queue_tts[0]['filename'], '-b:a', '128k', self.cfg.target_wav])
            return

        if self.cfg.voice_autorate:
            self.signal(text=tr("Sound speed alignment stage"))

        target_path = Path(self.cfg.target_wav)
        # If the same filename exists in the folder, append timestamp suffix
        if target_path.is_file() and target_path.stat().st_size > 0:
            self.cfg.target_wav = self.cfg.target_wav[
                                  :-4] + f'-{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}{target_path.suffix}'
        from videotrans.task._rate import TtsSpeedRate
        rate_inst = TtsSpeedRate(
            queue_tts=self.queue_tts,
            uuid=self.uuid,
            should_audiorate=self.cfg.voice_autorate if not self.cfg.target_sub.endswith('.txt') else False,
            raw_total_time=self.queue_tts[-1]['end_time'],
            target_audio=self.cfg.target_wav,
            cache_folder=self.cfg.cache_folder,
            remove_silent_mid=self.cfg.remove_silent_mid if not self.cfg.target_sub.endswith('.txt') else True,
            # Whether to remove gaps between subtitles: only effective when not auto-accelerating and file is srt; removed when txt dubbing, directly concatenating audio files
            align_sub_audio=False,  # Do not align subtitles: subtitle dubbing does not modify original subtitles, so alignment is meaningless
            event_sink=self.event_sink,
            cancellation_token=self.cancellation_token,
        )
        self.queue_tts = rate_inst.run()
        volume = self.cfg.volume.strip()
        if volume != '+0%':
            try:
                volume = 1 + float(volume.replace('%', '')) / 100
                tmp_name = self.cfg.cache_folder + f'/volume-{volume}-{Path(self.cfg.target_wav).name}'
                runffmpeg(['-y', '-i', self.cfg.target_wav, '-af', f"volume={volume}", tmp_name])
            except Exception as e:
                logger.exception(f'配音完毕后调节音量失败 {e}', exc_info=True)

    def task_done(self):
        if self._exit(): return
        from videotrans.util.help_ffmpeg import runffmpeg, remove_silence_wav
        if Path(self.cfg.target_wav).is_file():
            # Remove trailing silence
            remove_silence_wav(self.cfg.target_wav, rm_start=False)
            if self.out_ext.lower() != 'wav':
                runffmpeg(
                    ['-y', '-i', self.cfg.target_wav, f'{self.cfg.target_dir}/{self.cfg.noextname}.{self.out_ext}'])
                try:
                    Path(self.cfg.target_wav).unlink(missing_ok=True)
                except OSError:
                    pass

        self.set_end(True)
