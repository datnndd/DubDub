import sys
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf


class FakeVieNeuEngine:
    sample_rate = 48000

    def __init__(self):
        self.calls = []
        self.closed = False

    def get_preset_voice(self, role):
        return {"role": role}

    def infer_batch(self, texts, **options):
        self.calls.append((texts, options))
        return [np.zeros(960, dtype=np.float32) for _ in texts]

    def close(self):
        self.closed = True


class FakeParams(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.save_calls = 0

    def save(self):
        self.save_calls += 1


class TestVieNeuTTS:
    def test_registry_supports_vietnamese_and_english(self):
        from videotrans import tts

        assert tts.VIENEU_TTS == 34
        assert "VieNeu-TTS" in tts.TTS_NAME_LIST[tts.VIENEU_TTS]
        assert tts.VIENEU_TTS in tts.SUPPORT_CLONE
        assert tts.is_allow_lang("vi", tts.VIENEU_TTS) is True
        assert tts.is_allow_lang("en", tts.VIENEU_TTS) is True
        assert tts.is_allow_lang("zh", tts.VIENEU_TTS) is not True

    def test_gpu_batch_synthesis_writes_wav(self, monkeypatch, tmp_path):
        from videotrans.tts._vieneutts import VieNeuTTS

        engine = FakeVieNeuEngine()
        factory_args = {}

        def factory(**kwargs):
            factory_args.update(kwargs)
            return engine

        monkeypatch.setitem(sys.modules, "vieneu", SimpleNamespace(Vieneu=factory))
        queue = [
            {"text": "Xin chào", "role": "Phạm Tuyên", "filename": str(tmp_path / "one.wav")},
            {"text": "Đây là kiểm tra GPU", "role": "Phạm Tuyên", "filename": str(tmp_path / "two.wav")},
        ]
        tts = VieNeuTTS(queue_tts=queue, language="vi", is_cuda=True, uuid="test-vieneu")
        tts._exec()

        assert factory_args == {
            "mode": "v3turbo",
            "device": "cuda",
            "backend": "pytorch",
            "max_batch_size": 4,
        }
        assert engine.calls == [(["Xin chào", "Đây là kiểm tra GPU"], {"voice": {"role": "Phạm Tuyên"}})]
        assert engine.closed is True
        assert sf.info(tmp_path / "one.wav").samplerate == 48000
        assert sf.info(tmp_path / "two.wav").samplerate == 48000

    def test_custom_voice_is_saved_and_listed(self, monkeypatch, tmp_path):
        from videotrans import tts
        from videotrans.util import help_role

        params = FakeParams(vieneu_roles={})
        reference_audio = tmp_path / "narrator.wav"
        reference_audio.write_bytes(b"audio")
        monkeypatch.setattr(help_role, "params", params)
        monkeypatch.setattr(help_role, "get_vieneu_preset_roles", lambda: ["Binh"])

        voice_name = help_role.save_vieneu_custom_voice("Narrator", reference_audio)

        assert voice_name == "Narrator"
        assert help_role.role_menu(tts.VIENEU_TTS, "vi") == ["No", "clone", "Binh", "Custom: Narrator"]
        assert help_role.get_vieneu_custom_voice_path("Custom: Narrator") == reference_audio.resolve().as_posix()
        assert help_role.remove_vieneu_custom_voice("Narrator") is True
        assert params.save_calls == 2

    def test_custom_voice_rejects_preset_name(self, monkeypatch, tmp_path):
        from videotrans.util import help_role

        params = FakeParams(vieneu_roles={})
        reference_audio = tmp_path / "binh.wav"
        reference_audio.write_bytes(b"audio")
        monkeypatch.setattr(help_role, "params", params)
        monkeypatch.setattr(help_role, "get_vieneu_preset_roles", lambda: ["Binh"])

        with pytest.raises(ValueError):
            help_role.save_vieneu_custom_voice("Binh", reference_audio)

    def test_custom_voice_uses_reference_audio(self, monkeypatch, tmp_path):
        from videotrans.tts import _vieneutts
        from videotrans.tts._vieneutts import VieNeuTTS

        engine = FakeVieNeuEngine()
        reference_audio = tmp_path / "custom.wav"
        reference_audio.write_bytes(b"audio")
        monkeypatch.setitem(sys.modules, "vieneu", SimpleNamespace(Vieneu=lambda **_kwargs: engine))
        monkeypatch.setattr(
            _vieneutts,
            "get_vieneu_custom_voice_path",
            lambda role: reference_audio.as_posix() if role == "Custom: Narrator" else None,
        )
        tts = VieNeuTTS(
            queue_tts=[
                {"text": "Xin chào", "role": "Custom: Narrator", "filename": str(tmp_path / "result.wav")}
            ],
            language="vi",
            is_cuda=False,
            uuid="custom-vieneu",
        )

        voice_key, options = tts._inference_options({"role": "Custom: Narrator"})

        assert voice_key == ("custom", reference_audio.as_posix())
        assert options == {"ref_audio": reference_audio.as_posix()}
