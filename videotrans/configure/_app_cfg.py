# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from typing import Dict, Any, List

from videotrans.configure._i18n import _get_langjson_list


@dataclass
class AppCfg:
    """
    存储直接属于 config.py 的运行时属性 (原全局变量)。
    """
    NVIDIA_GPU_NUMS: int = -1

    stoped_uuid_set: set = field(default_factory=set)
    global_msg: List = field(default_factory=list)
    exit_soft: bool = False

    queue_novice: Dict = field(default_factory=dict)
    current_status: str = "stop"
    task_countdown: int = 0

    exec_mode: str = "web"
    video_codec: Any = None
    codec_cache: Dict = field(default_factory=dict)

    dubbing_role: Dict = field(default_factory=dict)
    SUPPORT_LANG: Dict = field(default_factory=dict)
    proxy: str = ''
    new_version_pvt: str = ""

    def __post_init__(self):
        self.SUPPORT_LANG = _get_langjson_list()

    def set_countdown(self, sec=86400):
        self.task_countdown = sec

    def rm_uuid(self, uuid=None):
        if not uuid:
            return
        try:
            self.stoped_uuid_set.remove(uuid)
        except KeyError:
            pass
