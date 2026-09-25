# -*- coding: utf-8 -*-
import json
import tempfile
import unittest
from pathlib import Path
import httpx
from fastapi import FastAPI

from videotrans.core.db import init_db, set_db_path
from videotrans.core import secret_store, storage_config
from videotrans.api.routes import settings as settings_routes


class TestSettingsAPI(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.tmp_dir.name) / "test_api_settings.db"
        set_db_path(db_path)
        init_db(db_path)
        secret_store.invalidate()

        self.app = FastAPI()
        settings_routes.register_routes(self.app)
        self.transport = httpx.ASGITransport(app=self.app)
        self.client = httpx.AsyncClient(transport=self.transport, base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        if self.tmp_dir:
            self.tmp_dir.cleanup()
        secret_store.invalidate()

    async def test_get_settings_snapshot_does_not_leak_keys(self):
        secret_store.set_secret("deepgram_apikey", "super-secret-key-123")
        resp = await self.client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()

        assert "providers" in data
        assert "storage" in data
        assert "general" in data

        dg = data["providers"]["deepgram"]
        assert dg["configured"] is True
        # Plaintext secret MUST NOT be present anywhere in response body
        text_body = resp.text
        assert "super-secret-key-123" not in text_body

    async def test_update_provider_settings_write_only(self):
        payload = {
            "apiKey": "sk-test-secret-value-xyz",
            "model": "nova-3",
        }
        resp = await self.client.put("/api/settings/providers/asr/deepgram", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["configured"] is True
        assert "sk-test-secret-value-xyz" not in json.dumps(data)

        # Confirm stored securely
        assert secret_store.get_secret("deepgram_apikey") == "sk-test-secret-value-xyz"

    async def test_probe_connection_success_and_failure(self):
        # 1. Missing key
        resp = await self.client.post("/api/settings/providers/asr/deepgram/test", json={})
        assert resp.status_code == 400

        # 2. Mocked successful probe
        async def mock_success(provider_id, api_key, base_url="", proxy=""):
            return True, "Mock connection succeeded"

        self.app.state.provider_probe = mock_success
        resp = await self.client.post(
            "/api/settings/providers/asr/deepgram/test",
            json={"apiKey": "valid-key"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "Mock connection succeeded" in data["message"]

        # 3. Mocked failed probe
        async def mock_fail(provider_id, api_key, base_url="", proxy=""):
            return False, "Authentication failed: 401 Unauthorized"

        self.app.state.provider_probe = mock_fail
        resp = await self.client.post(
            "/api/settings/providers/asr/deepgram/test",
            json={"apiKey": "invalid-key"},
        )
        assert resp.status_code == 400
        text = resp.text
        assert "401" in text

    async def test_storage_settings_get_and_update(self):
        import os

        resp = await self.client.get("/api/settings/storage")
        assert resp.status_code == 200
        data = resp.json()
        assert "paths" in data
        assert "usage" in data

        # Test path update
        with tempfile.TemporaryDirectory() as custom_dir:
            out_dir = str(Path(custom_dir) / "custom_output")
            up_resp = await self.client.put(
                "/api/settings/storage",
                json={"output_dir": out_dir},
            )
            assert up_resp.status_code == 200
            up_data = up_resp.json()
            assert up_data["ok"] is True

        # Test rejection of root path
        bad_resp = await self.client.put(
            "/api/settings/storage",
            json={"output_dir": "C:\\" if os.name == "nt" else "/"},
        )
        assert bad_resp.status_code == 400

    async def test_clean_temp_cache(self):
        resp = await self.client.post("/api/settings/storage/clean-temp")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "cleaned_bytes" in data

    async def test_update_general_settings(self):
        payload = {
            "proxy": "",
            "defaultSourceLanguage": "ja",
            "defaultTargetLanguage": "en",
            "crf": 21,
            "preset": "fast",
        }
        resp = await self.client.put("/api/settings/general", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
