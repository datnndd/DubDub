# -*- coding: utf-8 -*-
import hashlib
import json
import os
import re
import platform
import subprocess
import sys
import tempfile
import time
from dataclasses import is_dataclass, asdict
from functools import lru_cache
from pathlib import Path

from videotrans import VERSION
from videotrans.configure.config import tr, app_cfg, logger, ROOT_DIR, defaulelang
from videotrans.util.network import set_proxy, process_openai_api, is_connect_hf
from videotrans.util.prompts import get_prompt, qwenmt_glossary, get_prompt_file


def open_url(url: str = None):
    import webbrowser
    title_url_dict = {
        'bbs': "https://bbs.pyvideotrans.com",
        'ffmpeg': "https://www.ffmpeg.org/download.html",
        'git': "https://github.com/jianchang512/pyvideotrans",
        'issue': "https://github.com/jianchang512/pyvideotrans/issues",
        'hfmirrorcom': "https://pyvideotrans.com/819",
        'models': "https://github.com/jianchang512/stt/releases/tag/0.0",
        'stt': "https://github.com/jianchang512/stt/",
        'gtrans': "https://pyvideotrans.com/ocrsp",
        'cuda': "https://pyvideotrans.com/gpu",
        'website': "https://pyvideotrans.com",
        'help': "https://pyvideotrans.com",
        'xinshou': "https://pyvideotrans.com/getstart",
        "about": "https://pyvideotrans.com/about",
        'download': "https://github.com/jianchang512/pyvideotrans/releases",
    }
    if url and url.startswith("http"):
        return webbrowser.open_new_tab(url)
    if url and url in title_url_dict:
        return webbrowser.open_new_tab(title_url_dict[url])
    return


def vail_file(file=None):
    if not file:
        return False
    p = Path(file)
    if not p.exists() or not p.is_file():
        return False
    if p.stat().st_size == 0:
        return False
    return True


def shutdown_system():
    # 获取当前操作系统类型
    system = platform.system()

    if system == "Windows":
        # Windows 下的关机命令
        subprocess.call("shutdown /s /t 0", shell=True)
    elif system == "Linux":
        # Linux 下的关机命令
        subprocess.call("poweroff")
    elif system == "Darwin":
        # macOS 下的关机命令
        subprocess.call("sudo shutdown -h now", shell=True)
    else:
        logger.error(f"Unsupported system: {system}")


# 判断 novoice.mp4是否创建好
def is_novoice_mp4(novoice_mp4, noextname, uuid=None, *, event_sink=None, cancellation_token=None):
    # 预先创建好的
    # 判断novoice_mp4是否完成
    t = 0
    job_uuid = uuid or noextname

    if cancellation_token and cancellation_token.is_cancelled():
        return False

    if noextname not in app_cfg.queue_novice and vail_file(novoice_mp4):
        return True
    if noextname in app_cfg.queue_novice and app_cfg.queue_novice[noextname] == 'end':
        return True
    last_size = 0
    while True:
        if cancellation_token and cancellation_token.is_cancelled():
            return False
        if app_cfg.current_status != 'ing' or app_cfg.exit_soft:
            return False
        if vail_file(novoice_mp4):
            current_size = os.path.getsize(novoice_mp4)
            if 0 < last_size == current_size and t > 1200:
                return True
            last_size = current_size

        if noextname not in app_cfg.queue_novice:
            raise RuntimeError(f"{noextname} split no voice videoerror-1")
        if app_cfg.queue_novice[noextname].startswith('error:'):
            raise RuntimeError(f"{noextname} split no voice {app_cfg.queue_novice[noextname]}")

        if app_cfg.queue_novice[noextname] == 'ing':
            size = f'{round(last_size / 1024 / 1024, 2)}MB' if last_size > 0 else ""
            msg = f"{noextname} {tr('spilt audio and video')} {size}"
            if event_sink:
                event_sink({"uuid": job_uuid, "text": msg, "action": "novoice_wait"})
            time.sleep(1)
            t += 1
            continue
        return True


# 将字符串做 md5 hash处理
@lru_cache
def get_md5(input_string: str):
    md5 = hashlib.md5()
    md5.update(input_string.encode('utf-8'))
    return md5.hexdigest()


# 播放音频
def pygameaudio(filepath):
    import os
    if not os.path.exists(filepath):
        return
    import pygame
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(filepath)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        pygame.mixer.music.stop()
        pygame.mixer.quit()
    except Exception as e:
        logger.exception(f'pygame play error:{e}', exc_info=True)


def read_last_n_lines(filename, n=100):
    if not Path(filename).exists():
        return []
    from collections import deque
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            # 使用 deque 只保留最后 n 行
            last_lines = deque(file, maxlen=n)
        return list(last_lines)  # 返回列表形式
    except FileNotFoundError:
        return []
    except Exception:
        return []


# 序列化
def serial(data: object) -> str:
    if not isinstance(data, list):
        return json.dumps(asdict(data) if is_dataclass(data) else data)
    _newlist = []
    for it in data:
        _newlist.append(asdict(it) if is_dataclass(it) else it)
    return json.dumps(_newlist)


def check_new_version():
    # 查看当前最新版本信息
    try:
        import requests
        # 纯静态文件，仅返回版本信息字符串
        # 只获取当前软件版本号数字和操作系统类型(win32/macos/linux)
        url = f"https://pyvideotrans.com/version.json?version={VERSION}&os={sys.platform}"
        res = requests.get(url)
        res.raise_for_status()
        d = res.json()
        app_cfg.new_version_pvt = d['version']
    except Exception:
        pass


def _get_type_name(type_index, name_list):
    if type_index is None or type_index >= len(name_list):
        return '-'
    return name_list[type_index]


@lru_cache
def get_recogn_type(type_index=None):
    from videotrans.recognition import RECOGN_NAME_LIST
    return _get_type_name(type_index, RECOGN_NAME_LIST)


@lru_cache
def get_tanslate_type(type_index=None):
    from videotrans.translator import TRANSLASTE_NAME_LIST
    return _get_type_name(type_index, TRANSLASTE_NAME_LIST)


@lru_cache
def get_tts_type(type_index=None):
    from videotrans.tts import TTS_NAME_LIST
    return _get_type_name(type_index, TTS_NAME_LIST)


def atomic_write_json(data, target_path):
    target = Path(target_path)

    # 创建临时文件
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, suffix='.tmp', text=True)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(data, f)

    # 原子替换（此处即使进程崩溃，原文件依然完整）
    os.replace(tmp_name, target_path)
