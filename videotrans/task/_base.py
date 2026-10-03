import copy
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Union
from videotrans.configure.config import tr, app_cfg, logger
from videotrans.configure.base import BaseCon
from videotrans.task.taskcfg import TaskCfgBase, SrtItem

@dataclass
class BaseTask(BaseCon):
    # Configuration info, such as translation, dubbing, recognition channels, etc.
    cfg: TaskCfgBase = field(default_factory=TaskCfgBase, repr=False)
    # Progress tracking
    precent: int = 1
    # Original subtitle information requiring dubbing: List[dict]
    queue_tts: List = field(default_factory=list, repr=False)
    # Whether the task has ended
    hasend: bool = False
    # Whether speech recognition is needed
    should_recogn: bool = False
    # Whether subtitle translation is needed
    should_trans: bool = False
    # Whether dubbing is needed
    should_dubbing: bool = False
    # Whether vocal separation is needed
    should_separate: bool = False
    # Whether embedding dubbing or subtitles is needed
    should_hebing: bool = False

    def __post_init__(self):
        super().__post_init__()
        if self.cfg.uuid:
            self.uuid = self.cfg.uuid

    # Pre-processing, such as extracting audio from video, vocal/background separation, transcoding, etc.
    def prepare(self):
        pass

    # Speech recognition to create original language subtitles
    def recogn(self):
        pass

    # Speaker diarization: except for Funasr/Doubao ASR LLM/Deepgram, check if speakers already exist; Gemini/openai gpt4-dia generate speakers
    def diariz(self):
        pass

    # Translate original language subtitles to target language subtitles
    def trans(self):
        pass

    # Perform dubbing according to queue_tts
    def dubbing(self):
        pass

    # Dubbing speedup, video slowdown alignment
    def align(self):
        pass

    # Merge video, audio, and subtitles to generate result file
    def assembling(self):
        pass

    # Delete temporary files, move or copy, send success message
    def task_done(self):
        pass

    # Delete invalid files with size 0
    def _unlink_size0(self, file: Union[str, List[str]]):
        if not file: return
        files = [file] if isinstance(file, str) else file
        for f in files:
            p = Path(f)
            if p.exists() and p.stat().st_size == 0:
                p.unlink(missing_ok=True)

    # Save subtitle file to target folder
    def _save_srt_target(self, srt_list: List[SrtItem], file: str):
        from videotrans.util.help_srt import get_srt_from_list
        try:
            txt = get_srt_from_list(srt_list)
            with open(file, "w", encoding="utf-8", errors="ignore") as f:
                f.write(txt)
        except Exception as e:
            from videotrans.configure.excepts import VideoTransError
            raise VideoTransError(f'保存字幕前格式化srt失败:{file=}') from e

        self.signal(text=Path(file).read_text(encoding='utf-8', errors="ignore"), type='replace_subtitle')
        return True

    # If LLM resegmentation is enabled, skip this step; timelines change after LLM resegmentation and cannot align with original subtitles
    def check_target_sub(self, source_srt_list: List[SrtItem], target_srt_list: List[SrtItem]) -> List[SrtItem]:
        source_len = len(source_srt_list)
        target_len = len(target_srt_list)
        if source_len == target_len:
            logger.debug(f'原始语言字幕和目标语言字幕行数一致，均为 {source_len=}')
            return target_srt_list

        logger.warning(f'翻译结果行数{target_len}，原始字幕行数{source_len}，不一致,根据原始字幕时间轴获取对应目标字幕文本')
        # Based on original subtitle timeline, look up target subtitle text with matching timeline, more accurate
        _time2srt={}
        for it in target_srt_list:
            _time2srt[it['time']]=it['text']

        logger.debug(f'翻译结果行数{target_len} > 原始字幕行{source_len}，根据原始字幕的时间轴，到目标字幕内寻找同样时间轴的字幕文本')
        _source=copy.deepcopy(source_srt_list)
        for it in _source:
            it['text']=_time2srt.get(it['time'],'')
        return _source

    # Manually set as ended, on successful completion or error
    def set_end(self, succeed=False):
        self.hasend = True
        if succeed:
            self.precent = 100
            if self.cancellation_token is None and self.uuid in app_cfg.stoped_uuid_set:
                return
            self.signal(text=f"{self.cfg.name}", type='succeed')
            if self.event_sink is None:
                if app_cfg.exec_mode=="cli":
                    print(f'Save to:[ {self.cfg.target_dir} ]')
                else:
                    from videotrans.util.help_ffmpeg import send_notification
                    send_notification(tr('Succeed'), f"{self.cfg.basename}")
            # Clean up temporary files
            try:
                if self.cfg.cache_folder:
                    shutil.rmtree(self.cfg.cache_folder, ignore_errors=True)
            except Exception as e:
                logger.exception(f'任务结束后清理临时文件失败，跳过,{e}:{self.cfg.cache_folder=}', exc_info=True)
        if self.cancellation_token is None:
            app_cfg.stoped_uuid_set.add(self.uuid)
