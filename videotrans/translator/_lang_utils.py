from videotrans.configure.config import tr, params, logger
from videotrans.translator._constants import (
    GOOGLE_INDEX, AI_TRANS_CHANNELS,
)
from videotrans.translator._lang_codes import LANGNAME_DICT_REV, LANG_CODE
from videotrans.translator._registry import _ID_NAME_DICT


def get_code(show_text=None):
    # - None means no language selected; returns None, caller should handle accordingly
    # Returns original value if not found in LANG_CODE
    if not show_text or show_text in ['-', 'No']:
        return None
    if show_text == 'zh':
        return 'zh-cn'
    if show_text in LANG_CODE:
        return show_text
    return LANGNAME_DICT_REV.get(show_text, show_text)


# Based on displayed language and translation channel, get the source and target language codes required by that channel
# translate_type: translation channel index
# show_source: displayed original language name, '-', or language code
# show_target: displayed target language name, '-', or language code
# Returns natural language name of the language for AI channels
# Newly added language codes are returned directly
# '- No' is for backward compatibility with early informal notation
def get_source_target_code(*, show_source=None, show_target=None, translate_type=None):
    source_list = None
    target_list = None

    if show_source and show_source not in ['-', 'No']:
        if show_source in LANG_CODE:  # Is language code
            source_list = LANG_CODE[show_source]
        elif LANGNAME_DICT_REV.get(show_source):  # Is displayed language name
            source_list = LANG_CODE.get(LANGNAME_DICT_REV.get(show_source))
        elif show_source == 'zh':  # Special compatibility for zh
            source_list = LANG_CODE['zh-cn']

    if show_target and show_target not in ['-', 'No']:
        if show_target in LANG_CODE:  # Is language code
            target_list = LANG_CODE[show_target]
        elif LANGNAME_DICT_REV.get(show_target):  # Language name
            target_list = LANG_CODE.get(LANGNAME_DICT_REV.get(show_target))
        elif show_target == 'zh':
            # Special compatibility for zh
            target_list = LANG_CODE['zh-cn']

    # Neither found; may be a newly added language code
    if not source_list and not target_list:
        return show_source, show_target  # Return original input

    # If channel is not set, default to Google
    if translate_type == GOOGLE_INDEX or translate_type is None:
        return source_list[0] if source_list else show_source, target_list[0] if target_list else show_target

    # AI channels
    if translate_type in AI_TRANS_CHANNELS:
        return source_list[7] if source_list else show_source, target_list[7] if target_list else show_target

    return show_source, show_target


# Separately returns language name required by qwen-mt, qwen-tts, and qwen-asr
def get_language_qwen(langcode=None):
    if not langcode:
        return None
    if langcode == 'zh':
        langcode = 'zh-cn'
    _lang_list = LANG_CODE.get(langcode)
    return langcode if not _lang_list else _lang_list[9]


# Check if translation is allowed for current channel and target language
# E.g., DeepL does not support translation to certain target languages, check if API key is configured, etc.
# translate_type: translation channel
# show_target: target language name displayed after translation
# only_key=True: only checks key and api without checking target language
def is_allow_translate(*, translate_type=None, show_target=None, only_key=False, return_str=False):
    if translate_type == GOOGLE_INDEX or translate_type is None:
        return True

    _cls = _ID_NAME_DICT.get(translate_type)
    if not _cls:
        return True
    if _cls.key_name and not params.get(_cls.key_name):
        return "Please configure the SK or API information of the channel first."

    # If only checking whether API key is configured, return here
    if only_key:
        return True

    return True


# Get preset language for speech recognition, e.g. English speech, Chinese speech
# Determine based on original language, mostly identical to Google but retains only part before _
def get_audio_code(*, show_source=None):
    if not show_source or show_source in ['auto', '-']:
        return 'auto'
    source_list = LANG_CODE[show_source] if show_source in LANG_CODE else LANG_CODE.get(
        LANGNAME_DICT_REV.get(show_source))
    return source_list[0] if source_list else "auto"


# Get 3-letter ISO 639-2/T language code for MP4 soft subtitle embedding based on target language
# MKV videos need to call get_mkv_code with this returned code to get ISO 639-2/B
def get_subtitle_code(*, show_target=None):
    try:
        if show_target in LANG_CODE:
            return LANG_CODE[show_target][1]
        if show_target in LANGNAME_DICT_REV:
            return LANG_CODE[LANGNAME_DICT_REV[show_target]][1]
    except Exception as e:
        logger.error(f'获取字幕嵌入3为语言代码错误:{e}')
    return 'eng'

# If MKV soft subtitle, convert MP4 code to ISO 639-2/B standard code
def get_mkv_code(code):
    #  ISO 639-2/T :ISO 639-2/B
    langcode={
        "fra":"fre",
        "deu":"ger",
        "zho":"chi",
        "ces":"cze",
        "ell":"gre",
        "fas":"per",
        "msa":"may",
        "nld":"dut",
        "ron":"rum",
    }
    return langcode.get(code,code)
