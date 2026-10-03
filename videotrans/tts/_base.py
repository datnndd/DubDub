import asyncio,os
import concurrent
import copy
import inspect
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple
from tenacity import RetryError
from videotrans.configure.base import BaseCon
from videotrans.configure.config import tr, settings, logger, ROOT_DIR
from videotrans.configure import config
from videotrans.util.help_misc import vail_file,pygameaudio,get_tts_type

"""Shared execution for retained TTS providers."""


@dataclass
class BaseTTS(BaseCon):
    # Dubbing channel
    tts_type: int = 2
    # Queue storing subtitle information, extended SrtItem
    queue_tts: List[Dict[str, Any]] = field(default_factory=list, repr=False)
    # Reference audio or role dictionary
    roledict: Dict[str, Any] = field(default_factory=dict, repr=False)
    # queue_tts count
    len: int = field(init=False)
    # Language code
    language: Optional[str] = None
    # Unique uid
    uuid: Optional[str] = None
    # Whether to play immediately
    play: bool = False
    # Whether testing
    is_test: bool = False

    # Volume, speech rate and pitch use percentage/Hz string
    volume: Union[float, str] = field(default='+0%', init=False)
    rate: Union[float, str] = field(default='+0%', init=False)
    pitch: Union[float, str] = field(default='+0Hz', init=False)

    # Whether finished
    has_done: int = field(default=0, init=False)

    # Pause duration after each task
    wait_sec: float = float(settings.get('dubbing_wait', 0))
    # Concurrent thread count
    dub_nums: int = int(float(settings.get('dubbing_thread', 1)))
    # Stores message
    error: Union[str, Exception, None] = None
    # Dubbing API URL
    api_url: str = field(default='', init=False)
    # Enable CUDA (used on demand by local channels)
    is_cuda: bool = False
    local_dir: str = None
    # In single video mode, heavy local processes can wait for new tasks during dubbing proofreading
    # is_redubb is True indicates triggered from dubbing proofreading panel
    is_redubb:bool=False

    def __post_init__(self):
        super().__post_init__()
        Path(f'{config.TEMP_DIR}/{self.uuid}').mkdir(parents=True, exist_ok=True)
        self.queue_tts = copy.deepcopy(self.queue_tts)
        self.len = len(self.queue_tts)
        self._cleantts()

    # Subclass did not override _exec() method: run() -> _exec() -> _local_mul_thread() -> _item_task() -> _run()
    # Subclass overrides _exec() method: run() -> _exec()
    def run(self) -> None:
        if self._exit(): return
        from videotrans.configure.excepts import DubbingSrtError
        _tts_name=get_tts_type(self.tts_type)
        logger.debug(f'当前使用配音渠道：{_tts_name}')
        self.signal(text=f"{_tts_name} starting: [len={self.len}]")
        loop = None
        try:
            if hasattr(self, '_download'):
                self.signal(text=tr("check or download models"))
                self._download()
                self.signal(text=tr('Dubbing'))
            # Support channels implemented as async coroutine functions
            if inspect.iscoroutinefunction(self._exec):
                try:
                    # Check whether the current thread has a running event loop
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    # If the current thread already has a running loop (e.g. web framework main thread),
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(asyncio.run, self._exec())
                        future.result()
                else:
                    # If there is no running loop, directly use asyncio.run
                    asyncio.run(self._exec())
            else:
                # May invoke multithreading
                self._exec()
        except RetryError as e:
            raise e.last_attempt.exception()
        except (OSError,FileNotFoundError) as e:
            _e=str(e)
            if self.local_dir and ("no file named model.safetensors" in _e or os.path.basename(self.local_dir) in _e):
               from videotrans.configure.excepts import DownloadModelsError
               raise  DownloadModelsError(tr('model incomplete error',self.local_dir,tr('Help document')))
            raise
        except RuntimeError as e:
            logger.warning(f'TTS 线程运行时发生错误: {e}')
            if 'Event loop' in str(e):
                logger.warning("捕获到 'Event loop is closed' 错误，这通常是关闭时序问题。")
            else:
                raise


        # Play during preview or test
        if self.play:
            if vail_file(self.queue_tts[0]['filename']):
                return pygameaudio(self.queue_tts[0]['filename'])

            logger.error(f'试听配音时发生错误{self.error}')
            if isinstance(self.error, RetryError):
                raise self.error.last_attempt.exception()
            raise self.error if isinstance(self.error, Exception) else DubbingSrtError(str(self.error))

        # Record success count
        succeed_nums = 0
        for it in self.queue_tts:
            if self._exit(): return
            if not it['text'].strip() or vail_file(it['filename']):
                succeed_nums += 1
        # Only considered failure if all dubbings failed
        if succeed_nums < 1:
            if self._exit(): return
            logger.error(f'本次配音全部失败：{self.error}')
            if isinstance(self.error, Exception):
                raise self.error.last_attempt.exception() if isinstance(self.error, RetryError) else self.error

            raise DubbingSrtError(tr("Dubbing failed") + str(self.error))
        logger.debug(f'本次 {_tts_name} 配音成功 {succeed_nums} 个，失败 {self.len - succeed_nums} 个')
        self.signal(text=tr("Dubbing succeeded {}，failed {}", succeed_nums, self.len - succeed_nums))

    # If subclass does not override _exec(), this method is called by default
    # Checks if returned error is StopTask type; if so, terminates task directly
    def _local_mul_thread(self) -> None:
        if self._exit(): return
        from videotrans.configure.excepts import StopTask
        # Single subtitle line, no need for multithreading
        if len(self.queue_tts) == 1 or self.dub_nums == 1:
            logger.debug(f'设定最大配音线程: {self.dub_nums},实际 单线程配音, 待配音字幕长度: {self.len}, 配音后暂停{self.wait_sec}s')
            for k, item in enumerate(self.queue_tts):
                if self._exit(): return
                if not item.get('text').strip() or vail_file(item['filename']):
                    continue
                # Only record the last error
                error = self._item_task(item, k)
                self.error = error
                if error and isinstance(error, StopTask):
                    # Send termination signal; termination will add uuid to app_cfg.stop_uid
                    raise error

                self.signal(text=f'{tr("Dubbing")} [{k + 1}/{self.len}]')
                time.sleep(self.wait_sec)
            return

        all_task = []
        _wok=max(min(self.dub_nums, len(self.queue_tts)),2)
        pool = ThreadPoolExecutor(max_workers=_wok)
        logger.debug(f'设定配音最大线程数: {self.dub_nums},实际 {_wok} 线程配音, 待配音字幕长度: {self.len}')
        try:
            completed_tasks = 0
            for k, item in enumerate(self.queue_tts):
                if self._exit(): return
                if not item.get('text').strip() or vail_file(item['filename']):
                    completed_tasks += 1
                    continue
                future = pool.submit(self._item_task, item, k)
                all_task.append(future)

            if all_task:
                for task in as_completed(all_task):
                    if self._exit(): return
                    # Only record the last error
                    error = task.result()
                    self.error = error
                    if error and isinstance(error, StopTask):
                        # Send termination signal; termination will add uuid to app_cfg.stop_uid
                        raise error
                    completed_tasks += 1
                    self.signal(text=f"{tr('Dubbing')}: [{completed_tasks}/{self.len}] ...")
            self.signal(text=f"TTS ended ...")
        finally:
            # Only cancels queued tasks and prevents main thread from waiting
            pool.shutdown(wait=False)

    # Called by run(); subclasses may override to implement batch dubbing for entire queue_tts
    # If not overridden, enters multithreading, calling _item_task() per subtitle; subclass must implement _run()
    def _exec(self) -> None:
        self._local_mul_thread()

    # Each subtitle task, called in multiple threads by _local_mul_thread
    # data_item is each element in queue_tts
    # If subclass does not override _exec(), it must implement _run()
    # return: None on success; returns error message or raises exception on failure
    def _item_task(self, data_item: Union[Dict, List, None], idx: int = -1) -> Union[str, Exception, None]:
        if self._exit() or not data_item.get('text', '').strip() or vail_file(data_item.get('filename')):
            return
        # For unrecoverable errors like 404, invalid SK, unauthorized, send error signal directly without continuing other threads
        try:
            self.signal(text=f'{tr("Dubbing")} {idx}/{self.len}')
            return self._run(data_item,idx)
        except RetryError as e:
            logger.exception(f'\n第{idx}条字幕配音失败,字幕文本:{data_item}\n{e}', exc_info=True)
            return e.last_attempt.exception()
        except Exception as e:
            logger.exception(f'\n第{idx}条字幕配音失败,字幕文本:{data_item}\n{e}', exc_info=True)
            return e

    # If subclass did not override _exec, it must implement this method
    def _run(self, data_item: Union[Dict, List, None], idx: int = -1) -> Union[str, None]:
        raise NotImplemented

    # Text normalization and parameter cleanup (volume, etc.)
    def _cleantts(self) -> None:
        normalizer = None
        if settings.get('normal_text'):
            if self.language[:2] == 'zh':
                from videotrans.util.cn_tn import TextNorm
                normalizer = TextNorm(to_banjiao=True)
            elif self.language[:2] == 'en':
                from videotrans.util.en_tn import EnglishNormalizer
                normalizer = EnglishNormalizer()

        for i, it in enumerate(self.queue_tts):
            if it['text'].strip() and normalizer:
                try:
                    self.queue_tts[i]['text'] = normalizer(it['text'])
                except Exception as e:
                    logger.exception(f'文本规范化失败，忽略:{it["text"]=},{e}', exc_info=True)

        volume = self.queue_tts[0].get('volume', '+0%')
        volume = f'+{volume}' if re.match(r'^\d+(\.\d+)?%$', volume) else volume
        self.volume = '+0%' if not re.match(r'^[+-]\d+(\.\d+)?%$', volume) else volume

        rate = self.queue_tts[0].get('rate', '+0%')
        rate = f'+{rate}' if re.match(r'^\d+(\.\d+)?%$', rate) else rate
        self.rate = '+0%' if not re.match(r'^[+-]\d+(\.\d+)?%$', rate) else rate

        pitch = self.queue_tts[0].get('pitch', '+0Hz').replace('hz', 'Hz')
        pitch = f'+{pitch}' if re.match(r'^\d+(\.\d+)?Hz$', pitch, re.I) else pitch
        self.pitch = '+0Hz' if not re.match(r'^[+-]\d+(\.\d+)?Hz$', pitch, flags=re.I) else pitch

        logger.debug(f'{self.volume=}, {self.rate=}, {self.pitch=}')

    # Convert percentage rate/volume to decimal float
    def get_speed(self) -> float:
        speed = 1.0
        try:
            speed = round(1 + float(self.rate.replace('%', '')) / 100, 1)
        except (TypeError,ValueError):
            pass
        return speed

    def get_volume(self) -> float:
        volume = 1.0
        try:
            volume = round(1 + float(self.volume.replace('%', '')) / 100, 1)
        except (TypeError,ValueError):
            pass
        return volume

    def get_pitch(self) -> float:
        pitch = 1.0
        try:
            pitch = round(float(re.sub(r'[hz%]', '', self.pitch,flags=re.I)), 1)
        except (TypeError,ValueError):
            pass
        return pitch

    # Return reference audio and reference text
    def get_ref_wav(self, item) -> Tuple[str, str]:
        role = item['role']
        ref_wav, ref_text = None, None
        if role == 'clone':
            ref_wav = item.get('ref_wav', '')
            ref_text = item.get('ref_text').strip()
        elif role in self.roledict:
            if not isinstance(self.roledict[role],dict):
                return ref_wav,ref_text
            ref_text = self.roledict[role]['ref_text']
            ref_wav = ROOT_DIR + f"/f5-tts/{role}"

        if not ref_wav or not Path(ref_wav).exists():
            raise RuntimeError(tr('The role {} does not exist', role))
        return ref_wav, ref_text
