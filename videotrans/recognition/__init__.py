from typing import List, Type, Union

from videotrans import ChannelProvider, get_class
from videotrans.configure import contants
from videotrans.configure.config import app_cfg, params, tr
from videotrans.recognition._base import BaseRecogn
from videotrans.task.taskcfg import SrtItem

# Provider IDs are contiguous because the desktop UI stores QComboBox indexes.
QWENASR = 0
Deepgram = 1
GEMINI_SPEECH = 2
GOOGLE_SPEECH = 3
ElevenLabs = 4
FASTER_WHISPER = 5

ALLOW_CHANGE_MODEL = [QWENASR, Deepgram, FASTER_WHISPER]

_ID_NAME_DICT = {
    QWENASR: ChannelProvider(f"Qwen-ASR({tr('Built-in')})", imp="._qwenasrlocal"),
    Deepgram: ChannelProvider("Deepgram.com", key_name="deepgram_apikey", imp="._deepgram"),
    GEMINI_SPEECH: ChannelProvider(tr("Gemini AI"), key_name="gemini_key", imp="._gemini"),
    GOOGLE_SPEECH: ChannelProvider(tr("Google Speech to Text"), imp="._google"),
    ElevenLabs: ChannelProvider("ElevenLabs.io", key_name="elevenlabstts_key", imp="._elevenlabs"),
    FASTER_WHISPER: ChannelProvider("Whisper Large-v3", imp="._whisper"),
}
RECOGN_NAME_LIST = [provider.name for provider in _ID_NAME_DICT.values()]


def get_model_by_type(recogn_type: int) -> List[str]:
    if recogn_type == QWENASR:
        return ["1.7B", "0.6B"]
    if recogn_type == Deepgram:
        return contants.DEEPGRAM_MODEL
    if recogn_type == GEMINI_SPEECH:
        return ["gemini-flash-latest"]
    if recogn_type == GOOGLE_SPEECH:
        return ["google-web-speech"]
    if recogn_type == ElevenLabs:
        return ["scribe_v2"]
    if recogn_type == FASTER_WHISPER:
        return ["large-v3"]
    return []


def is_allow_lang(langcode: str = None, recogn_type: int = None, model_name=None):
    if recogn_type not in _ID_NAME_DICT:
        return tr("Unsupported speech recognition provider.")
    if (langcode == "auto" or not langcode) and recogn_type not in [
        FASTER_WHISPER,
        GEMINI_SPEECH,
        ElevenLabs,
    ]:
        return tr("Automatic language detection is not supported by this recognition provider.")
    return True


def is_input_api(recogn_type: int = None, return_str=False):
    provider = _ID_NAME_DICT.get(recogn_type)
    if not provider:
        return tr("Unsupported speech recognition provider.")
    if provider.key_name and not params.get(provider.key_name):
        return tr("Please configure the API information of the selected recognition provider first.")
    return True


def run(
    *,
    detect_language=None,
    audio_file=None,
    cache_folder=None,
    model_name=None,
    uuid=None,
    recogn_type: int = QWENASR,
    is_cuda=None,
    subtitle_type=0,
    max_speakers=-1,
    llm_post=False,
    recogn2pass=False,
    event_sink=None,
    cancellation_token=None,
) -> Union[List[SrtItem], None]:
    if app_cfg.exit_soft or (uuid and uuid in app_cfg.stoped_uuid_set):
        return None
    kwargs = {
        "detect_language": detect_language,
        "audio_file": audio_file,
        "cache_folder": cache_folder,
        "model_name": model_name,
        "uuid": uuid,
        "is_cuda": is_cuda,
        "subtitle_type": subtitle_type,
        "recogn_type": recogn_type,
        "max_speakers": max_speakers,
        "llm_post": llm_post,
        "recogn2pass": recogn2pass,
        "event_sink": event_sink,
        "cancellation_token": cancellation_token,
    }
    cls: Union[Type[BaseRecogn], None] = get_class(recogn_type, "recognition", _ID_NAME_DICT)
    if not cls:
        raise RuntimeError(f"No this Recognition Channel:{recogn_type=}")
    return cls(**kwargs).run()  # type: ignore
