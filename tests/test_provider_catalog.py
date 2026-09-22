import json
from pathlib import Path

from videotrans import recognition, translator, tts
from videotrans.configure._app_params import AppParams, PROVIDER_CATALOG_VERSION


class _EmptyProviderSettings:
    def get(self, _key, default=None):
        return default


def test_asr_catalog_is_the_supported_contiguous_set():
    assert list(recognition._ID_NAME_DICT) == list(range(6))
    assert [
        recognition.QWENASR,
        recognition.Deepgram,
        recognition.GEMINI_SPEECH,
        recognition.GOOGLE_SPEECH,
        recognition.ElevenLabs,
        recognition.FASTER_WHISPER,
    ] == list(range(6))
    assert recognition.get_model_by_type(recognition.QWENASR) == ["1.7B", "0.6B"]
    assert recognition.get_model_by_type(recognition.FASTER_WHISPER) == ["large-v3"]


def test_translation_catalog_is_the_supported_contiguous_set():
    assert list(translator._ID_NAME_DICT) == list(range(4))
    assert [
        translator.GOOGLE_INDEX,
        translator.CHATGPT_INDEX,
        translator.GEMINI_INDEX,
        translator.DEEPSEEK_INDEX,
    ] == list(range(4))
    assert translator.AI_TRANS_CHANNELS == [1, 2, 3]


def test_tts_catalog_is_the_supported_contiguous_set_with_vieneu_default():
    assert list(tts._ID_NAME_DICT) == list(range(4))
    assert [
        tts.ELEVENLABS_TTS,
        tts.OMNIVOICE_TTS,
        tts.VIENEU_TTS,
        tts.GEMINI_TTS,
    ] == list(range(4))
    assert tts.DEFAULT_TTS == tts.VIENEU_TTS
    assert tts.TTS_NAME_LIST == [
        "ElevenLabs",
        "OmniVoice(Built-in)",
        "VieNeu-TTS",
        "Gemini TTS",
    ]
    assert [provider.imp for provider in tts._ID_NAME_DICT.values()] == [
        "._elevenlabs",
        "._omnivoice",
        "._vieneutts",
        "._geminitts",
    ]


def test_missing_provider_credentials_return_errors(monkeypatch):
    monkeypatch.setattr(recognition, "params", _EmptyProviderSettings())
    monkeypatch.setattr(tts, "params", _EmptyProviderSettings())
    monkeypatch.setattr("videotrans.translator._lang_utils.params", _EmptyProviderSettings())

    assert "configure" in recognition.is_input_api(recognition.Deepgram).lower()
    assert "configure" in tts.is_input_api(tts.ELEVENLABS_TTS).lower()
    assert "configure" in translator.is_allow_translate(
        translate_type=translator.CHATGPT_INDEX,
        show_target="vi",
    ).lower()


def test_provider_execution_forwards_job_context(monkeypatch):
    captured = []

    class FakeProvider:
        def __init__(self, **kwargs):
            captured.append(kwargs)

        def run(self):
            return []

    event_sink = object()
    cancellation_token = object()

    monkeypatch.setattr("videotrans.recognition.get_class", lambda *_args: FakeProvider)
    recognition.run(
        recogn_type=recognition.FASTER_WHISPER,
        event_sink=event_sink,
        cancellation_token=cancellation_token,
    )

    monkeypatch.setattr("videotrans.translator._runner.get_class", lambda *_args: FakeProvider)
    translator.run(
        translate_type=translator.CHATGPT_INDEX,
        text_list=[],
        source_code="en",
        target_code="vi",
        event_sink=event_sink,
        cancellation_token=cancellation_token,
    )

    monkeypatch.setattr(tts, "get_class", lambda *_args: FakeProvider)
    tts.run(
        queue_tts=[{"text": "hello"}],
        tts_type=tts.VIENEU_TTS,
        event_sink=event_sink,
        cancellation_token=cancellation_token,
    )

    assert len(captured) == 3
    assert all(kwargs["event_sink"] is event_sink for kwargs in captured)
    assert all(kwargs["cancellation_token"] is cancellation_token for kwargs in captured)


def test_removed_provider_implementations_are_absent():
    root = Path(__file__).parents[1] / "videotrans"
    removed = [
        root / "recognition" / "_funasr.py",
        root / "recognition" / "_openairecognapi.py",
        root / "recognition" / "_whisperx.py",
        root / "translator" / "_microsoft.py",
        root / "translator" / "_deepl.py",
        root / "translator" / "_tencent.py",
        root / "translator" / "_ali.py",
        root / "tts" / "_edgetts.py",
        root / "tts" / "_openaitts.py",
        root / "tts" / "_qwenttslocal.py",
        root / "tts" / "_chatterbox.py",
    ]
    assert not [path for path in removed if path.exists()]


def test_retained_tts_implementations_are_present():
    root = Path(__file__).parents[1] / "videotrans" / "tts"
    retained = ["_elevenlabs.py", "_omnivoice.py", "_vieneutts.py", "_geminitts.py"]
    assert [name for name in retained if not (root / name).is_file()] == []


def test_language_codes_match_google_and_ai_provider_contracts():
    assert translator.get_source_target_code(
        show_source="en", show_target="zh-cn", translate_type=translator.GOOGLE_INDEX
    ) == ("en", "zh-cn")
    assert translator.get_source_target_code(
        show_source="en", show_target="zh-cn", translate_type=translator.CHATGPT_INDEX
    ) == ("English", "Simplified Chinese")


def test_public_language_helpers_remain_available():
    assert translator.get_code("zh") == "zh-cn"
    assert translator.get_audio_code(show_source="-") == "auto"
    assert translator.get_subtitle_code(show_target="vi") == "vie"
    assert translator.get_mkv_code("fra") == "fre"


def test_legacy_saved_provider_ids_are_migrated_once(tmp_path):
    config_path = tmp_path / "params.json"
    config_path.write_text(json.dumps({
        "provider_catalog_version": 1,
        "recogn_type": 22,
        "stt_recogn_type": 0,
        "translate_type": 4,
        "trans_translate_type": 6,
        "tts_type": 34,
        "dubb_tts_type": 22,
        "f5tts_role": "",
    }), encoding="utf-8")

    migrated = AppParams(_json_path=str(config_path))

    assert migrated.recogn_type == recognition.Deepgram
    assert migrated.model_name == "nova-3"
    assert migrated.stt_recogn_type == recognition.FASTER_WHISPER
    assert migrated.stt_model_name == "large-v3"
    assert migrated.translate_type == translator.CHATGPT_INDEX
    assert migrated.trans_translate_type == translator.GEMINI_INDEX
    assert migrated.tts_type == tts.VIENEU_TTS
    assert migrated.dubb_tts_type == tts.ELEVENLABS_TTS
    assert json.loads(config_path.read_text(encoding="utf-8"))["provider_catalog_version"] == PROVIDER_CATALOG_VERSION


def test_removed_legacy_tts_selection_migrates_to_vieneu(tmp_path):
    config_path = tmp_path / "params.json"
    config_path.write_text(json.dumps({
        "provider_catalog_version": 2,
        "tts_type": 0,
        "dubb_tts_type": 30,
        "f5tts_role": "",
    }), encoding="utf-8")

    migrated = AppParams(_json_path=str(config_path))

    assert migrated.tts_type == tts.VIENEU_TTS
    assert migrated.dubb_tts_type == tts.VIENEU_TTS
