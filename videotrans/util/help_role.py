import json
import re
from functools import lru_cache
from pathlib import Path
from typing import List

from videotrans.configure import contants
from videotrans.configure.config import ROOT_DIR, logger, params, tr


@lru_cache
def get_elevenlabs_role(force=False, raise_exception=False):
    from . import help_misc

    jsonfile = f"{ROOT_DIR}/videotrans/voicejson/elevenlabs.json"
    namelist = ["No"]
    if help_misc.vail_file(jsonfile):
        with open(jsonfile, "r", encoding="utf-8-sig") as file:
            cache = json.loads(file.read())
            namelist.extend(item["name"] for item in cache.values())
    if not force and namelist:
        params["elevenlabstts_role"] = namelist
        return namelist
    try:
        from elevenlabs import ElevenLabs

        client = ElevenLabs(api_key=params.get("elevenlabstts_key", ""))
        voices = client.voices.get_all()
        result = {}
        for voice in voices.voices:
            name = re.sub(r"[^a-zA-Z0-9_ -]+", "", voice.name, flags=re.I | re.S).strip()
            result[name] = {"name": name, "voice_id": voice.voice_id}
        namelist = ["No", *result]
        Path(jsonfile).write_text(json.dumps(result), encoding="utf-8")
        params["elevenlabstts_role"] = namelist
        return namelist
    except Exception as error:
        logger.exception(f"Failed to get ElevenLabs voices: {error}", exc_info=True)
        if raise_exception:
            raise
    return []


def get_f5tts_role():
    """Return reference voices shared by the retained OmniVoice provider."""
    rolelist = {"No": "No", "clone": "clone"}
    if not params.get("f5tts_role", "").strip():
        return rolelist
    for item in params.get("f5tts_role", "").strip().split("\n"):
        parts = item.strip().split("#")
        if len(parts) == 2:
            rolelist[parts[0]] = {"ref_wav": parts[0], "ref_text": parts[1]}
    return rolelist


VIENEU_CUSTOM_ROLE_PREFIX = "Custom: "


@lru_cache
def get_vieneu_preset_roles():
    try:
        from importlib.resources import files

        voice_file = files("vieneu").joinpath("assets").joinpath("voices_v3_turbo.json")
        voice_data = json.loads(voice_file.read_text(encoding="utf-8"))
        return list(voice_data.get("presets", {}).keys())
    except (
        ImportError,
        ModuleNotFoundError,
        FileNotFoundError,
        AttributeError,
        OSError,
        json.JSONDecodeError,
    ):
        return []


def get_vieneu_custom_voice_map():
    saved_roles = params.get("vieneu_roles", {})
    if not isinstance(saved_roles, dict):
        return {}
    return {
        str(name): str(audio_path)
        for name, audio_path in saved_roles.items()
        if str(name).strip() and str(audio_path).strip()
    }


def get_vieneu_role():
    custom_roles = get_vieneu_custom_voice_map()
    custom_names = sorted(custom_roles, key=str.casefold)
    return ["No", "clone", *get_vieneu_preset_roles(), *[
        f"{VIENEU_CUSTOM_ROLE_PREFIX}{name}" for name in custom_names
    ]]


def get_vieneu_custom_voice_path(role):
    if not str(role).startswith(VIENEU_CUSTOM_ROLE_PREFIX):
        return None
    name = str(role)[len(VIENEU_CUSTOM_ROLE_PREFIX):]
    return get_vieneu_custom_voice_map().get(name)


def save_vieneu_custom_voice(name, audio_path):
    voice_name = " ".join(str(name).split())
    if not voice_name:
        raise ValueError(tr("VieNeu voice name is required"))
    if voice_name.casefold() in {"no", "clone"}:
        raise ValueError(tr("VieNeu voice name is reserved: {}", voice_name))
    if voice_name.casefold() in {preset.casefold() for preset in get_vieneu_preset_roles()}:
        raise ValueError(tr("VieNeu voice name conflicts with a preset voice: {}", voice_name))

    reference_audio = Path(audio_path).expanduser()
    if not reference_audio.is_file():
        raise ValueError(tr("VieNeu reference audio file does not exist: {}", audio_path))

    custom_roles = get_vieneu_custom_voice_map()
    custom_roles[voice_name] = reference_audio.resolve().as_posix()
    params["vieneu_roles"] = custom_roles
    params.save()
    return voice_name


def remove_vieneu_custom_voice(name):
    custom_roles = get_vieneu_custom_voice_map()
    if str(name) not in custom_roles:
        return False
    del custom_roles[str(name)]
    params["vieneu_roles"] = custom_roles
    params.save()
    return True


def role_menu(tts_type, langcode=None) -> List:
    from videotrans import tts

    if tts_type == tts.ELEVENLABS_TTS:
        return get_elevenlabs_role()
    if tts_type == tts.OMNIVOICE_TTS:
        return list(get_f5tts_role().keys())
    if tts_type == tts.VIENEU_TTS:
        return get_vieneu_role()
    if tts_type == tts.GEMINI_TTS:
        return contants.GEMINITTS_ROLES.split(",")
    return ["No"]
