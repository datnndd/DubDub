import time,os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union

from tenacity import RetryError

from videotrans import translator
from videotrans.configure.base import BaseCon
from videotrans.configure.config import tr, settings, logger, TEMP_ROOT
from videotrans.task.taskcfg import SrtItem
from videotrans.util.help_srt import get_subtitle_from_srt,cleartext
from videotrans.util.help_misc import get_md5,serial

@dataclass
class BaseTrans(BaseCon):
    # Translation channel
    translate_type: int = 0
    # List storing subtitles to be translated
    text_list: List[SrtItem] = None
    # Unique task ID
    uuid: Optional[str] = None
    # Do not use cache during tests
    is_test: bool = False
    # Original language code
    source_code: str = ""
    # Target language code
    target_code: str = ""
    # For AI channels, natural language representation of target language; equals target_code for other channels
    target_language_name: str = ""

    # Translation API URL
    api_url: str = field(default="", init=False)
    # Model name
    model_name: str = field(default="", init=False)
    # Number of subtitle lines translated concurrently
    trans_thread: int = 5
    # Pause seconds after translation
    wait_sec: float = float(settings.get('translation_wait', 0))
    # Whether AI translation channel and send full SRT format is selected
    aisendsrt: Optional[bool] = None
    local_dir: str = None

    def __post_init__(self):
        super().__post_init__()
        Path(TEMP_ROOT + f'/translate_cache').mkdir(parents=True, exist_ok=True)
        requested_mode = settings.get('aisendsrt', False) if self.aisendsrt is None else self.aisendsrt
        self.aisendsrt = bool(requested_mode) and self.translate_type in translator.AI_TRANS_CHANNELS
        if self.aisendsrt:
            self.trans_thread = int(settings.get('aitrans_thread', 20)) if not settings.get('aitrans_context') else len(self.text_list)
        else:
            self.trans_thread = int(settings.get('trans_thread', 5))

    def _item_task(self, data: Union[List[str], str]):
        raise NotImplemented()

    # Actual operations run -> run_text|run_srt -> _item_task
    def run(self) -> List[SrtItem]:
        try:
            if hasattr(self, '_download'):
                self.signal(text=tr("check or download models"))
                self._download()
                self.signal(text=tr("Transation subtitles"))
            if not self.aisendsrt:
                # Is text list: [str, ...]
                source_text = [t['text'].replace("\n", " ") for t in self.text_list]
                return self._run_text(
                    [source_text[i:i + self.trans_thread] for i in range(0, len(source_text), self.trans_thread)])
            # Is SRT-formatted subtitle list: [SrtItem, ...]
            return self._run_srt(
                    [self.text_list[i:i + self.trans_thread] for i in range(0, len(self.text_list), self.trans_thread)])        
        except RetryError as e:
            raise e.last_attempt.exception()
        except (OSError,FileNotFoundError) as e:
            _e=str(e)
            if self.local_dir and ("no file named model.safetensors" in _e or os.path.basename(self.local_dir) in _e):
               from videotrans.configure.excepts import DownloadModelsError
               raise  DownloadModelsError(tr('model incomplete error',self.local_dir,tr('Help document')))
            raise
        finally:
            if hasattr(self, '_unload'):
                self._unload()


    def _run_text(self, split_source_text: List[List[str]]):
        # Traditional translation channels or AI translation channels translate line-by-line
        """
        split_source_text=[
            ["subtitle text 1", "subtitle text 2", ...],
            ["subtitle text 1", "subtitle text 2", ...],
            ["subtitle text 1", "subtitle text 2", ...],
            ...
        ]
        """
        target_list = []
        logger.debug(f'以纯文本行形式翻译，每次翻译{self.trans_thread}行，翻译后暂停{self.wait_sec}s')
        
        for i, it in enumerate(split_source_text):
            """ it=['Hello my friend', 'Second line'] At this point _item_task receives list[str] """
            if self._exit(): return
            self.signal(text=tr('starttrans') + f' {i} ')
            result = self._get_cache(it)
            if not result:
                result = cleartext(self._item_task(it))
                self._set_cache(it, result)
            sep_res = result.split("\n")
            for x, result_item in enumerate(sep_res):
                if x < len(it):
                    target_list.append(result_item.strip())
                    self.signal(text=result_item + "\n", type='subtitle')
            # Fill empty lines when line count does not match
            if len(sep_res) < len(it):
                logger.debug(f'行数不匹配，原始：{len(it)}, 结果：{len(sep_res)}\n{it=}\n{sep_res=}')
                tmp = ["" for x in range(len(it) - len(sep_res))]
                target_list += tmp
            time.sleep(self.wait_sec)
        max_i = len(target_list)
        logger.debug(f'原始行数:{len(self.text_list)},翻译后行数:{max_i}')
        _empty_line = 0
        for i, it in enumerate(self.text_list):
            text = target_list[i].strip() if i < max_i else ""
            if not text:
                _empty_line += 1
            self.text_list[i]['text'] = text

        if _empty_line >= len(self.text_list):
            from videotrans.configure.excepts import TranslateSrtError
            raise TranslateSrtError(tr("Translate result is empty")+f'\n{self.api_url}')
        return self.text_list

    # Send full subtitle format content for translation
    # At this point _item_task receives an SRT-formatted string
    def _run_srt(self, split_source_text: List[List[SrtItem]]):
        """
        split_source_text=[
            [{text:"",start_time:"",line:""},{...},...]
            ...
        ]
        """
        logger.debug(f'以SRT字幕块翻译，每次翻译 {self.trans_thread} 条字幕块，翻译后暂停{self.wait_sec}s')
        from videotrans.configure.excepts import TranslateSrtError
        raws_list = []
        for i, it in enumerate(split_source_text):
            if self._exit(): return
            self.signal(text=tr('starttrans') + f' {i} ')
            # Form valid SRT-formatted string
            srt_str = "\n\n".join(
                [f"{srt_dict['line']}\n{srt_dict['time']}\n{srt_dict['text'].strip()}" for srt_dict in it])
            result = self._get_cache(srt_str)
            if not result:
                result = self._item_task(srt_str)
                if not result.strip():
                    raise TranslateSrtError(tr("Translate result is empty")+f'\n{self.api_url}')
                self._set_cache(it, result)

            self.signal(text=result, type='subtitle')
            raws_list.extend(get_subtitle_from_srt(result, is_file=False))
            time.sleep(self.wait_sec)

        _empty_line = 0
        for it in raws_list:
            if not it['text'].strip():
                _empty_line += 1
        if _empty_line >= len(raws_list):
            raise TranslateSrtError(tr("Translate result is empty")+f'\n{self.api_url}')
        logger.debug(f'原始字幕行数：{len(self.text_list)}, 翻译后行数:{len(raws_list)}')
        return raws_list

    def _set_cache(self, it, res_str):
        if not res_str.strip(): return
        file_cache = TEMP_ROOT + f'/translate_cache/{self._get_key(it)}.txt'
        Path(file_cache).write_text(res_str, encoding='utf-8')

    def _get_cache(self, it) -> Union[str,None]:
        if self.is_test: return
        file_cache = TEMP_ROOT + f'/translate_cache/{self._get_key(it)}.txt'
        if Path(file_cache).exists():
            logger.debug(f'本次跳过翻译，使用缓存')
            return Path(file_cache).read_text(encoding='utf-8')
        return

    def _get_key(self, it) -> str:
        it=serial(it)
        key_str = f'{self.translate_type}-{self.api_url}-{self.aisendsrt}-{self.model_name}-{self.source_code}-{self.target_code}-{it}'
        return get_md5(key_str)
