import asyncio
import io
import threading
import time
from pathlib import Path

from aiohttp import FormData
from aiohttp.test_utils import TestClient, TestServer
import pytest

from tests import webui_support as webui
from videotrans import translator, tts
from videotrans.task.orchestrator import (
    CancellationToken,
    EventKind,
    TaskEvent,
    TaskRequest,
    TaskResult,
    TaskStatus,
)


def test_new_frontend_is_the_only_webui():
    app = webui.create_app()
    routes = {route.resource.canonical for route in app.router.routes()}

    assert "/" in routes
    assert "/api/options" in routes
    assert "/api/media" in routes
    assert "/api/jobs" in routes
    assert "/api/jobs/{job_id}" in routes
    assert "/api/asr-settings/{provider_id}" in routes
    assert "/api/asr-settings/{provider_id}/test" in routes
    assert "/api/translation-settings/{provider_id}" in routes
    assert "/api/translation-settings/{provider_id}/test" in routes
    assert "gradio" not in Path(webui.__file__).read_text(encoding="utf-8").lower()


def test_frontend_static_and_html_have_no_cache_headers():
    app = webui.create_app()

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            res_html = await client.get("/")
            assert res_html.status == 200
            assert "no-cache" in res_html.headers.get("Cache-Control", "")
            assert "no-store" in res_html.headers.get("Cache-Control", "")

            res_js = await client.get("/js/app.js")
            assert res_js.status == 200
            assert "no-cache" in res_js.headers.get("Cache-Control", "")
            assert "no-store" in res_js.headers.get("Cache-Control", "")
        finally:
            await client.close()

    asyncio.run(scenario())


def test_frontend_reload_mode_reports_changes_and_injects_browser_refresh(tmp_path, monkeypatch):
    frontend = tmp_path / "frontend"
    (frontend / "js").mkdir(parents=True)
    (frontend / "css").mkdir()
    (frontend / "assets").mkdir()
    (frontend / "index.html").write_text("<html><body></body></html>", encoding="utf-8")
    script = frontend / "js" / "app.js"
    script.write_text("const version = 1;", encoding="utf-8")
    monkeypatch.setattr(webui, "FRONTEND_DIR", frontend)

    app = webui.create_app(upload_dir=tmp_path / "uploads", reload=True)

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            html = await (await client.get("/")).text()
            assert "/__dev_reload__" in html
            assert "location.reload()" in html

            before = await (await client.get("/__dev_reload__")).json()
            script.write_text("const version = 2;", encoding="utf-8")
            after = await (await client.get("/__dev_reload__")).json()
            assert after["version"] != before["version"]
        finally:
            await client.close()

    asyncio.run(scenario())


def test_main_accepts_reload_flag(monkeypatch):
    captured = {}
    monkeypatch.setattr("sys.argv", ["webui.py", "--reload", "--port", "8765"])
    monkeypatch.setattr(webui.web, "run_app", lambda app, **kwargs: captured.update(app=app, **kwargs))

    webui.main()

    assert captured["port"] == 8765
    assert captured["app"]["reload"] is True


def test_build_task_params_maps_supported_frontend_fields(tmp_path, monkeypatch):
    source = tmp_path / "sample video.mp4"
    source.write_bytes(b"video")
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    temp_dir.mkdir()
    monkeypatch.setattr(webui, "TEMP_DIR", str(temp_dir))
    monkeypatch.setattr(webui, "OUTPUT_DIR", output_dir)
    params = webui.build_task_params(source, {
        "sourceLanguage": "en",
        "targetLanguage": "fr",
        "recognType": webui.recognition.Deepgram,
        "translateType": translator.CHATGPT_INDEX,
        "ttsType": 3,
        "modelName": "nova-3",
        "timingMode": "video",
        "translationMode": "line",
        "speakerDiarization": True,
        "speakerCount": 2,
        "voiceRate": "+10%",
    }, job_type="asr")

    assert params["name"] == source.resolve().as_posix()
    assert params["source_language_code"] == "en"
    assert params["target_language_code"] == "fr"
    assert params["recogn_type"] == webui.recognition.Deepgram
    assert params["model_name"] == "nova-3"
    assert params["translate_type"] == translator.CHATGPT_INDEX
    assert params["aisendsrt"] is False
    assert params["tts_type"] == 3
    assert params["voice_role"] == "No"
    assert params["remove_noise"] is False
    assert params["enable_diariz"] is True
    assert params["nums_diariz"] == 2
    assert params["voice_rate"] == "+10%"
    assert params["voice_autorate"] is False
    assert params["video_autorate"] is False
    assert params["align_sub_audio"] is False
    assert params["subtitle_type"] == 0
    assert params["only_out_dubbed_audio"] is True
    assert params["embed_bgm"] is False
    assert Path(params["cache_folder"]).is_relative_to(temp_dir)


def test_build_task_params_rejects_unknown_backend_choices(tmp_path):
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"video")

    with pytest.raises(ValueError, match="ASR engine"):
        webui.build_task_params(source, {
            "sourceLanguage": next(iter(translator.LANGNAME_DICT)),
            "targetLanguage": next(iter(translator.LANGNAME_DICT)),
            "recognType": 9999,
            "translateType": 0,
            "ttsType": 0,
        })

    with pytest.raises(ValueError, match="translation mode"):
        webui.build_task_params(source, {
            "sourceLanguage": "zh-cn",
            "targetLanguage": "vi",
            "recognType": webui.recognition.Deepgram,
            "modelName": "nova-3",
            "translateType": translator.CHATGPT_INDEX,
            "translationMode": "invented",
            "ttsType": 0,
        })


def test_build_task_params_rejects_removed_provider_and_mismatched_model(tmp_path):
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"video")

    with pytest.raises(ValueError, match="Unknown ASR engine"):
        webui.build_task_params(source, {
            "sourceLanguage": "zh-cn",
            "targetLanguage": "vi",
            "recognType": 99,
            "translateType": 0,
            "ttsType": 0,
        })

    with pytest.raises(ValueError, match="not supported by Deepgram"):
        webui.build_task_params(source, {
            "sourceLanguage": "zh-cn",
            "targetLanguage": "vi",
            "recognType": webui.recognition.Deepgram,
            "modelName": "large-v3",
            "translateType": 0,
            "ttsType": 0,
        })

    with pytest.raises(ValueError, match="Unknown translation engine"):
        webui.build_task_params(source, {
            "sourceLanguage": "zh-cn",
            "targetLanguage": "vi",
            "recognType": webui.recognition.Deepgram,
            "modelName": "nova-3",
            "translateType": 99,
            "ttsType": 0,
        })


def test_build_task_params_maps_each_timing_mode(tmp_path):
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"video")
    common = {
        "sourceLanguage": "zh-cn",
        "targetLanguage": "vi",
        "recognType": webui.recognition.Deepgram,
        "modelName": "nova-3",
        "translateType": translator.CHATGPT_INDEX,
        "translationMode": "srt",
        "ttsType": 0,
    }

    voice = webui.build_task_params(source, {**common, "timingMode": "voice"})
    video = webui.build_task_params(source, {**common, "timingMode": "video"})
    align = webui.build_task_params(source, {**common, "timingMode": "align"})

    assert (voice["voice_autorate"], voice["video_autorate"], voice["align_sub_audio"]) == (True, False, False)
    assert voice["aisendsrt"] is True
    assert (video["voice_autorate"], video["video_autorate"], video["align_sub_audio"]) == (False, True, False)
    assert (align["voice_autorate"], align["video_autorate"], align["align_sub_audio"]) == (False, False, True)


def test_api_provider_configuration_is_required_before_start():
    class EmptySettings:
        def get(self, _key, default=None):
            return default

    with pytest.raises(ValueError, match="Configure Deepgram API settings"):
        webui.ensure_asr_configured(webui.recognition.Deepgram, EmptySettings())

    webui.ensure_asr_configured(webui.recognition.FASTER_WHISPER, EmptySettings())
    with pytest.raises(ValueError, match="Configure OpenAI ChatGPT settings"):
        webui.ensure_translation_configured(translator.CHATGPT_INDEX, EmptySettings())
    webui.ensure_translation_configured(translator.GOOGLE_INDEX, EmptySettings())


def test_options_expose_only_supported_asr_providers_and_safe_configuration_state(tmp_path):
    class FakeSettings:
        def __init__(self):
            self.values = {
                "deepgram_apikey": "configured-secret",
                "elevenlabstts_key": "",
                "chatgpt_api": "https://api.openai.com/v1",
                "chatgpt_key": "translation-secret",
                "chatgpt_model": "gpt-5-mini",
                "gemini_key": "",
                "gemini_model": "gemini-2.5-flash",
                "deepseek_key": "",
                "deepseek_model": "deepseek-v4-flash",
            }

        def get(self, key, default=None):
            return self.values.get(key, default)

        def __setitem__(self, key, value):
            self.values[key] = value

        def save(self):
            pass

    app = webui.create_app(upload_dir=tmp_path / "uploads", settings_store=FakeSettings())

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            response = await client.get("/api/options")
            assert response.status == 200
            data = await response.json()
            providers = data["asrProviders"]
            assert [item["label"] for item in providers] == [
                "Qwen-ASR",
                "Deepgram",
                "Gemini STT",
                "Google STT API",
                "ElevenLabs",
                "Whisper Large-v3",
            ]
            assert data["defaults"] == {
                "sourceLanguage": "zh-cn",
                "targetLanguage": "vi",
                "recognType": webui.recognition.Deepgram,
                "modelName": "nova-3",
                "timingMode": "voice",
                "translateType": translator.GOOGLE_INDEX,
                "translationMode": "srt" if webui.runtime_config.settings.get("aisendsrt", True) else "line",
                "ttsType": tts.VIENEU_TTS,
            }
            assert data["voices"] == [
                [tts.ELEVENLABS_TTS, "ElevenLabs"],
                [tts.OMNIVOICE_TTS, "OmniVoice(Built-in)"],
                [tts.VIENEU_TTS, "VieNeu-TTS"],
                [tts.GEMINI_TTS, "Gemini TTS"],
            ]
            state_source = (Path(webui.ROOT_DIR) / "frontend" / "js" / "state.js").read_text(encoding="utf-8")
            prepare_source = (
                Path(webui.ROOT_DIR) / "frontend" / "js" / "screens" / "Stage1Prepare.js"
            ).read_text(encoding="utf-8")
            stage3_source = (
                Path(webui.ROOT_DIR) / "frontend" / "js" / "screens" / "Stage3VoiceDubbing.js"
            ).read_text(encoding="utf-8")
            assert "ttsType: 2" in state_source
            assert "updateBackendConfig('ttsType', Number(this.value))" in stage3_source
            assert "updateBackendConfig('ttsType', Number(this.value))" not in prepare_source
            assert data["translationModes"] == [
                {"id": "line", "label": "Line-by-line", "description": "Send plain subtitle text in batches."},
                {"id": "srt", "label": "Send SRT", "description": "Send subtitle blocks with timestamps and structure."},
            ]
            assert next(item for item in providers if item["id"] == "qwen-asr")["models"] == ["1.7B", "0.6B"]
            assert next(item for item in providers if item["id"] == "whisper-large-v3")["models"] == ["large-v3"]
            deepgram = next(item for item in providers if item["id"] == "deepgram")
            assert deepgram["requiresSettings"] is True
            assert deepgram["configured"] is True
            assert deepgram["testable"] is True
            assert next(item for item in providers if item["id"] == "google-stt")["testable"] is True
            assert next(item for item in providers if item["id"] == "qwen-asr")["testable"] is False
            translation_providers = data["translationProviders"]
            assert [item["label"] for item in translation_providers] == [
                "Google Translate",
                "OpenAI ChatGPT",
                "Gemini",
                "DeepSeek",
            ]
            openai = next(item for item in translation_providers if item["id"] == "openai")
            assert openai["configured"] is True
            assert openai["baseUrl"] == "https://api.openai.com/v1"
            assert openai["model"] == "gpt-5-mini"
            assert "gpt-5-mini" in openai["models"]
            assert "configured-secret" not in await response.text()
            assert "translation-secret" not in await response.text()
        finally:
            await client.close()

    asyncio.run(scenario())


def test_translation_settings_save_and_test_supported_providers(tmp_path):
    class FakeSettings:
        def __init__(self):
            self.values = {}
            self.save_count = 0

        def get(self, key, default=None):
            return self.values.get(key, default)

        def __setitem__(self, key, value):
            self.values[key] = value

        def save(self):
            self.save_count += 1

    tested = []

    def fake_test(translate_type, aisendsrt):
        tested.append((translate_type, aisendsrt))
        return "Hello, my friend"

    settings = FakeSettings()
    app = webui.create_app(
        upload_dir=tmp_path / "uploads",
        settings_store=settings,
        translation_tester=fake_test,
    )

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            cases = [
                ("openai", "chatgpt", "https://api.openai.com/v1", "gpt-5-mini"),
                ("gemini", "gemini", "https://gemini.example.test", "gemini-2.5-flash"),
                ("deepseek", "deepseek", "https://deepseek.example.test/v1", "deepseek-v4-flash"),
            ]
            for provider_id, prefix, base_url, model in cases:
                payload = {"baseUrl": base_url, "apiKey": f"{provider_id}-secret", "model": model}
                response = await client.post(f"/api/translation-settings/{provider_id}", json=payload)
                assert response.status == 200
                body = await response.json()
                assert body["configured"] is True
                assert "secret" not in str(body)
                assert settings.values[f"{prefix}_api"] == base_url
                assert settings.values[f"{prefix}_key"] == f"{provider_id}-secret"
                assert settings.values[f"{prefix}_model"] == model

            response = await client.post("/api/translation-settings/openai/test", json={
                "baseUrl": "https://api.openai.com/v1",
                "model": "gpt-5-mini",
                "translationMode": "srt",
            })
            assert response.status == 200
            assert await response.json() == {"ok": True, "message": "Connection successful", "result": "Hello, my friend"}
            assert tested == [(translator.CHATGPT_INDEX, True)]

            response = await client.post("/api/translation-settings/google", json={})
            assert response.status == 404
            response = await client.post("/api/translation-settings/unsupported/test", json={})
            assert response.status == 404
        finally:
            await client.close()

    asyncio.run(scenario())


def test_translation_backends_use_configured_base_urls(monkeypatch):
    from videotrans.translator import _chatgpt, _deepseek, _gemini

    class FakeParams:
        values = {
            "chatgpt_api": "https://openai.example.test/v1",
            "chatgpt_key": "key",
            "chatgpt_model": "gpt-test",
            "chatgpt_max_token": 100,
            "gemini_api": "https://gemini.example.test",
            "gemini_key": "key",
            "gemini_model": "gemini-test",
            "deepseek_api": "https://deepseek.example.test/v1",
            "deepseek_key": "key",
            "deepseek_model": "deepseek-test",
            "deepseek_max_token": 100,
        }

        def get(self, key, default=None):
            return self.values.get(key, default)

    fake = FakeParams()
    monkeypatch.setattr(_chatgpt, "params", fake)
    monkeypatch.setattr(_deepseek, "params", fake)
    monkeypatch.setattr(_gemini, "params", fake)
    common = {
        "text_list": [],
        "source_code": "zh-cn",
        "target_code": "en",
        "target_language_name": "English",
    }

    assert _chatgpt.ChatGPT(translate_type=translator.CHATGPT_INDEX, **common).api_url == "https://openai.example.test/v1"
    assert _gemini.Gemini(translate_type=translator.GEMINI_INDEX, **common).api_url == "https://gemini.example.test"
    assert _deepseek.DeepSeek(translate_type=translator.DEEPSEEK_INDEX, **common).api_url == "https://deepseek.example.test/v1"


def test_asr_settings_saves_only_supported_provider_keys(tmp_path):
    class FakeSettings:
        def __init__(self):
            self.values = {"deepgram_apikey": "", "gemini_key": "", "elevenlabstts_key": ""}
            self.save_count = 0

        def get(self, key, default=None):
            return self.values.get(key, default)

        def __setitem__(self, key, value):
            self.values[key] = value

        def save(self):
            self.save_count += 1

    settings = FakeSettings()
    app = webui.create_app(upload_dir=tmp_path / "uploads", settings_store=settings)

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            response = await client.post("/api/asr-settings/deepgram", json={"apiKey": "new-secret"})
            assert response.status == 200
            assert await response.json() == {"configured": True}
            assert settings.values["deepgram_apikey"] == "new-secret"
            assert settings.save_count == 1

            response = await client.post("/api/asr-settings/google-stt", json={"apiKey": "not-allowed"})
            assert response.status == 404
            response = await client.post("/api/asr-settings/gemini-stt", json={"apiKey": "  "})
            assert response.status == 400
        finally:
            await client.close()

    asyncio.run(scenario())


def test_asr_settings_tests_selected_third_party_model(tmp_path):
    class FakeSettings:
        def __init__(self):
            self.values = {"deepgram_apikey": "", "gemini_key": "", "elevenlabstts_key": ""}
            self.save_count = 0

        def get(self, key, default=None):
            return self.values.get(key, default)

        def __setitem__(self, key, value):
            self.values[key] = value

        def save(self):
            self.save_count += 1

    tested = []

    def fake_test(recogn_type, model_name):
        tested.append((recogn_type, model_name))
        return "Hello from the ASR sample"

    settings = FakeSettings()
    app = webui.create_app(
        upload_dir=tmp_path / "uploads",
        settings_store=settings,
        asr_tester=fake_test,
    )

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            response = await client.post("/api/asr-settings/deepgram/test", json={
                "apiKey": "deepgram-secret",
                "model": "nova-3",
            })
            assert response.status == 200
            assert await response.json() == {
                "ok": True,
                "message": "Connection successful",
                "model": "nova-3",
                "result": "Hello from the ASR sample",
            }
            assert settings.values["deepgram_apikey"] == "deepgram-secret"
            assert tested == [(webui.recognition.Deepgram, "nova-3")]

            response = await client.post("/api/asr-settings/google-stt/test", json={"model": "google-web-speech"})
            assert response.status == 200
            assert tested[-1] == (webui.recognition.GOOGLE_SPEECH, "google-web-speech")

            response = await client.post("/api/asr-settings/deepgram/test", json={"model": "large-v3"})
            assert response.status == 400
            response = await client.post("/api/asr-settings/qwen-asr/test", json={"model": "1.7B"})
            assert response.status == 404
        finally:
            await client.close()

    asyncio.run(scenario())


def test_asr_connection_tester_uses_production_recognition_with_selected_model(tmp_path, monkeypatch):
    calls = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        assert Path(kwargs["cache_folder"]).is_dir()
        return [{"text": "Sample transcript"}]

    monkeypatch.setattr(webui, "TEMP_DIR", str(tmp_path))
    monkeypatch.setattr(webui.recognition, "run", fake_run)

    result = webui.test_asr_provider(webui.recognition.Deepgram, "nova-3")

    assert result == "Sample transcript"
    assert calls[0]["recogn_type"] == webui.recognition.Deepgram
    assert calls[0]["model_name"] == "nova-3"
    assert calls[0]["detect_language"] == "zh-cn"
    assert calls[0]["audio_file"].endswith("videotrans/assets/no-remove.wav")
    assert not Path(calls[0]["cache_folder"]).exists()


def test_job_manager_reports_events_outputs_and_terminal_status(tmp_path, monkeypatch):
    output = tmp_path / "dubbed.mp4"
    output.write_bytes(b"result")

    def fake_run(_request, sink, _token):
        sink(TaskEvent("task", EventKind.RUNNING, "prepare"))
        sink(TaskEvent("task", EventKind.PROGRESS, "prepare", progress=42.0))
        return TaskResult("task", TaskStatus.SUCCEEDED, tmp_path, (output,))

    monkeypatch.setattr(webui, "run", fake_run)
    manager = webui.JobManager(runner=fake_run)
    job = manager.submit({"name": "unused"}, media_id="media")

    deadline = time.time() + 2
    while job.snapshot()["status"] not in {"succeeded", "failed", "cancelled"} and time.time() < deadline:
        time.sleep(0.01)
    snapshot = job.snapshot()

    assert snapshot["status"] == "succeeded"
    assert snapshot["stage"] == "prepare"
    assert snapshot["progress"] == 100.0
    assert snapshot["outputs"] == [{
        "name": "dubbed.mp4",
        "url": f"/api/jobs/{job.id}/outputs/0",
    }]


def test_cancel_is_scoped_to_one_job():
    manager = webui.JobManager()
    first = webui.JobRecord("first", webui.CancellationToken())
    second = webui.JobRecord("second", webui.CancellationToken())
    manager._jobs = {"first": first, "second": second}

    manager.cancel("first")

    assert first.token.is_cancelled()
    assert not second.token.is_cancelled()


def test_media_ingest_and_job_submission_are_end_to_end(tmp_path, monkeypatch):
    release = threading.Event()
    received = {}
    output = tmp_path / "dubbed.mp4"
    output.write_bytes(b"result")

    def fake_probe(path):
        assert Path(path).read_bytes() == b"synthetic video"
        return {
            "time": 12_345,
            "width": 1280,
            "height": 720,
            "video_fps": 25,
            "video_codec_name": "h264",
            "audio_codec_name": "aac",
            "format_name": "QuickTime / MOV",
            "bit_rate": 1_500_000,
            "audio_sample_rate": 48_000,
            "audio_channels": 2,
            "video_streams": 1,
            "streams_audio": 1,
        }

    def fake_run(request, sink, _token):
        received.update(request.params)
        sink(TaskEvent("task", EventKind.STAGE_STARTED, "prepare", message="Preparing media"))
        release.wait(2)
        return TaskResult("task", TaskStatus.SUCCEEDED, tmp_path, (output,))

    manager = webui.JobManager(runner=fake_run)
    monkeypatch.setattr(webui, "getset_gpu", lambda: None)
    app = webui.create_app(job_manager=manager, upload_dir=tmp_path / "uploads", media_probe=fake_probe)

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            form = FormData()
            form.add_field("file", io.BytesIO(b"synthetic video"), filename="sample clip.mp4", content_type="video/mp4")
            response = await client.post("/api/media", data=form)
            assert response.status == 201
            media = await response.json()
            assert media["filename"] == "sample clip.mp4"
            assert media["durationMs"] == 12_345
            assert media["sizeBytes"] == len(b"synthetic video")
            assert media["resolution"] == "1280x720"
            assert media["videoCodec"] == "h264"
            assert media["container"] == "QuickTime / MOV"
            assert media["bitrate"] == 1_500_000
            assert media["audioSampleRate"] == 48_000
            assert media["audioChannels"] == 2

            language_codes = list(translator.LANGNAME_DICT)
            payload = {
                "mediaId": media["id"],
                "options": {
                    "sourceLanguage": language_codes[0],
                    "targetLanguage": language_codes[-1],
                    "recognType": webui.recognition.FASTER_WHISPER,
                    "modelName": "large-v3",
                    "translateType": 0,
                    "ttsType": 0,
                },
            }
            response = await client.post("/api/jobs", json=payload)
            assert response.status == 202
            job = await response.json()

            duplicate = await client.post("/api/jobs", json=payload)
            assert duplicate.status == 409
            assert "already running" in (await duplicate.text()).lower()

            release.set()
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                response = await client.get(f"/api/jobs/{job['id']}")
                snapshot = await response.json()
                if snapshot["status"] == "succeeded":
                    break
                await asyncio.sleep(0.01)
            assert snapshot["status"] == "succeeded"
            assert received["source_language_code"] == language_codes[0]
            assert received["target_language_code"] == language_codes[-1]
            assert received["name"].endswith("sample clip.mp4")
        finally:
            release.set()
            await client.close()

    asyncio.run(scenario())


def test_media_ingest_rejects_unreadable_media_and_removes_upload(tmp_path):
    def failed_probe(_path):
        raise ValueError("not readable media")

    upload_dir = tmp_path / "uploads"
    app = webui.create_app(upload_dir=upload_dir, media_probe=failed_probe)

    async def scenario():
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            form = FormData()
            form.add_field("file", io.BytesIO(b"broken"), filename="broken.mp4", content_type="video/mp4")
            response = await client.post("/api/media", data=form)
            assert response.status == 400
            assert "not readable media" in (await response.text()).lower()
            assert not list(upload_dir.glob("*"))
        finally:
            await client.close()

    asyncio.run(scenario())


def test_prepare_job_stops_at_transcript_checkpoint_and_skips_render_work(tmp_path, monkeypatch):
    received = {}

    def fake_run(request, sink, token, *, stop_after_stage=None):
        received["stop_after_stage"] = stop_after_stage
        received["params"] = dict(request.params)
        sink(TaskEvent("task", EventKind.STAGE_STARTED, "recogn"))
        return TaskResult("task", TaskStatus.SUCCEEDED, tmp_path, ())

    monkeypatch.setattr(webui, "run", fake_run)
    request = TaskRequest({
        "name": str(tmp_path / "input.mp4"),
        "target_dir": str(tmp_path / "output"),
    })
    (tmp_path / "input.mp4").write_bytes(b"video")

    result = webui.run_prepare_review(request, lambda event: None, CancellationToken())

    assert result.status == TaskStatus.SUCCEEDED
    assert received["stop_after_stage"] == "diariz"


def test_prepare_polling_does_not_remount_video():
    app_source = (Path(webui.FRONTEND_DIR) / "js" / "app.js").read_text(encoding="utf-8")
    state_source = (Path(webui.FRONTEND_DIR) / "js" / "state.js").read_text(encoding="utf-8")
    footer_source = (Path(webui.FRONTEND_DIR) / "js" / "components" / "StatusFooter.js").read_text(encoding="utf-8")

    assert "renderStatusOnly" in app_source
    assert "scope === 'status'" in app_source
    assert "this.notify(terminal ? 'full' : 'status')" in state_source
    assert "data-status-footer" in footer_source


def test_prepare_frontend_uses_ingested_media_and_real_disabled_state():
    state_source = (Path(webui.FRONTEND_DIR) / "js" / "state.js").read_text(encoding="utf-8")
    footer_source = (Path(webui.FRONTEND_DIR) / "js" / "components" / "StatusFooter.js").read_text(encoding="utf-8")

    assert "fetch('/api/media'" in state_source
    assert "mediaId" in state_source
    assert "disabled" in footer_source


def test_prepare_video_preview_has_sound_and_seek_controls():
    prepare_source = (Path(webui.FRONTEND_DIR) / "js" / "screens" / "Stage1Prepare.js").read_text(encoding="utf-8")
    state_source = (Path(webui.FRONTEND_DIR) / "js" / "state.js").read_text(encoding="utf-8")
    video_tag = prepare_source.split("<video data-source-preview", 1)[1].split(">", 1)[0]

    assert "controls" in video_tag
    assert "muted" not in video_tag
    assert 'type="range"' in prepare_source
    assert "seekPreview" in prepare_source
    assert "seekPreview" in state_source


def test_prepare_diagnostics_is_visible_at_tablet_and_desktop_widths():
    prepare_source = (Path(webui.FRONTEND_DIR) / "js" / "screens" / "Stage1Prepare.js").read_text(encoding="utf-8")

    assert 'col-span-12 md:col-span-7' in prepare_source
    assert 'col-span-12 md:col-span-5' in prepare_source
    assert "backend.error" in prepare_source
    assert "Speaker analysis runs during the processing workflow" not in prepare_source
    assert "Preview Audio Stems" not in prepare_source
    assert "Replace Video" not in prepare_source


def test_prepare_frontend_defaults_and_provider_specific_models_are_connected():
    prepare_source = (Path(webui.FRONTEND_DIR) / "js" / "screens" / "Stage1Prepare.js").read_text(encoding="utf-8")
    translation_source = (Path(webui.FRONTEND_DIR) / "js" / "components" / "TranslationConfig.js").read_text(encoding="utf-8")
    stage2_source = (Path(webui.FRONTEND_DIR) / "js" / "screens" / "Stage2ReviewTranscript.js").read_text(encoding="utf-8")
    state_source = (Path(webui.FRONTEND_DIR) / "js" / "state.js").read_text(encoding="utf-8")

    assert 'code: "zh-cn"' in state_source
    assert 'code: "vi"' in state_source
    assert "asrProviders" in prepare_source
    assert "selectedProvider.models" in prepare_source
    assert "openAsrSettings" in prepare_source
    assert "testAsrConnection" in state_source
    assert "Test connection" in prepare_source
    assert "timingMode" in prepare_source
    assert "timingMode: this.state.languages.timingMode" in state_source
    assert "renderTranslationConfig" not in prepare_source
    assert "renderTranslationConfig" in stage2_source
    assert "translationProviders" in translation_source
    assert "openTranslationSettings" in translation_source
    assert "testTranslationConnection" in state_source


def test_prepare_audio_processing_uses_existing_backend_features():
    prepare_source = (Path(webui.FRONTEND_DIR) / "js" / "screens" / "Stage1Prepare.js").read_text(encoding="utf-8")
    state_source = (Path(webui.FRONTEND_DIR) / "js" / "state.js").read_text(encoding="utf-8")

    assert "Speaker Classification" in prepare_source
    assert "Noise Reduction" in prepare_source
    assert "Number of speakers" in prepare_source
    assert "Auto-isolate" not in prepare_source
    assert "-24 dB de-reverb" not in prepare_source
    assert "speakerDiarization: false" in state_source
    assert "removeNoise: false" in state_source
    assert "speakerCount: this.state.engines.speakerCount" in state_source


def test_prepare_uses_existing_line_and_srt_translation_modes():
    prepare_source = (Path(webui.FRONTEND_DIR) / "js" / "screens" / "Stage1Prepare.js").read_text(encoding="utf-8")
    translation_source = (Path(webui.FRONTEND_DIR) / "js" / "components" / "TranslationConfig.js").read_text(encoding="utf-8")
    stage2_source = (Path(webui.FRONTEND_DIR) / "js" / "screens" / "Stage2ReviewTranscript.js").read_text(encoding="utf-8")
    state_source = (Path(webui.FRONTEND_DIR) / "js" / "state.js").read_text(encoding="utf-8")

    assert "Tone &amp; Register Preset" not in prepare_source
    assert "Conversational ★" not in prepare_source
    assert "Formal Lecture" not in prepare_source
    assert 'tone: "conversational"' not in state_source
    assert "renderTranslationConfig" not in prepare_source
    assert "renderTranslationConfig" in stage2_source
    assert "Translation Mode" in translation_source
    assert "translationModes" in translation_source
    assert "mode.label" in translation_source
    assert "mode.description" in translation_source
    assert 'translationMode: "srt"' in state_source
    assert "updateBackendConfig('translationMode'" in translation_source
    for provider in ("chatgpt", "gemini", "deepseek"):
        assert (Path(webui.ROOT_DIR) / "videotrans" / "prompts" / "text" / f"{provider}.txt").is_file()
        assert (Path(webui.ROOT_DIR) / "videotrans" / "prompts" / "srt" / f"{provider}.txt").is_file()
