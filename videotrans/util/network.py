# -*- coding: utf-8 -*-
import os
import re
import sys
from functools import lru_cache
from pathlib import Path

from videotrans.configure.config import app_cfg, logger, ROOT_DIR


def set_proxy(set_val=''):
    if set_val == 'del':
        app_cfg.proxy = ''
        if os.environ.get('HTTP_PROXY'):
            del os.environ['HTTP_PROXY']
        if os.environ.get('HTTPS_PROXY'):
            del os.environ['HTTPS_PROXY']
        return

    if set_val:
        # 设置代理
        set_val = set_val.lower()
        if not set_val.startswith("http") and not set_val.startswith('sock'):
            set_val = f"http://{set_val}"
        app_cfg.proxy = set_val
        os.environ['HTTP_PROXY'] = set_val
        os.environ['HTTPS_PROXY'] = set_val
        return set_val

    # 获取代理
    http_proxy = app_cfg.proxy or os.environ.get('HTTP_PROXY') or os.environ.get('HTTPS_PROXY')
    if http_proxy:
        http_proxy = http_proxy.lower()
        if not http_proxy.startswith("http") and not http_proxy.startswith('sock'):
            http_proxy = f"http://{http_proxy}"
        return http_proxy
    if sys.platform != 'win32':
        return None
    try:
        import winreg
        # 打开 Windows 注册表
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r'Software\Microsoft\Windows\CurrentVersion\Internet Settings') as key:
            # 读取代理设置
            proxy_enable, _ = winreg.QueryValueEx(key, 'ProxyEnable')
            proxy_server, _ = winreg.QueryValueEx(key, 'ProxyServer')
            if proxy_enable == 1 and proxy_server:
                # 是否需要设置代理
                proxy_server = proxy_server.lower()
                if not proxy_server.startswith("http") and not proxy_server.startswith('sock'):
                    proxy_server = "http://" + proxy_server

                return proxy_server
    except Exception:
        pass
    return None


@lru_cache
def process_openai_api(url=""):
    if not url:
        return "https://api.openai.com/v1"
    if not url.startswith('http'):
        url = 'http://' + url

    # 删除末尾 /
    url = url.rstrip('/').lower()
    if url.find(".openai.com") > -1:
        return "https://api.openai.com/v1"

    if url.endswith('/v1'):
        return url

    # 存在 /v1/xx的，改为 /v1
    if url.find('/v1/chat/') > -1:
        return re.sub(r'/v1.*$', '/v1', url, flags=re.I | re.S)

    return url


def is_connect_hf() -> bool:
    # 强制使用 huggingface.co
    if Path(f'{ROOT_DIR}/huggingface.txt').exists():
        return True
    try:
        import requests
        logger.debug(f'{app_cfg.proxy=}')
        if app_cfg.proxy:
            requests.head('https://huggingface.co', timeout=5, proxies={"http": app_cfg.proxy, "https": app_cfg.proxy})
        else:
            requests.head('https://huggingface.co', timeout=5)
    except Exception:
        os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
        logger.debug('无法连接 huggingface.co, 使用镜像替换: hf-mirror.com')
        return False
    else:
        os.environ['HF_ENDPOINT'] = 'https://huggingface.co'
        logger.debug('可以使用 huggingface.co')
        return True
