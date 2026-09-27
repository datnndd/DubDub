"""
conftest.py — sets up mocks for heavy dependencies so videotrans
modules can be imported without a full optional model-runtime installation.

Only mocks packages that are genuinely NOT installed.
"""

import importlib
import sys
from unittest.mock import MagicMock


def _is_installed(name):
    """Check if a package is actually importable (not just in sys.modules)."""
    try:
        spec = importlib.util.find_spec(name)
        return spec is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


_HAS_TORCH = _is_installed("torch")
_HAS_REQUESTS = _is_installed("requests")
_HAS_TENACITY = _is_installed("tenacity")
_HAS_OPENAI = _is_installed("openai")
_HAS_DEEPGRAM = _is_installed("deepgram")
_HAS_ELEVENLABS = _is_installed("elevenlabs")
_HAS_AIOHTTP = _is_installed("aiohttp")
_HAS_HTTPCORE = _is_installed("httpcore")
_HAS_HTTPX = _is_installed("httpx")
_HAS_HF_HUB = _is_installed("huggingface_hub")
_HAS_TENVAD = _is_installed("ten_vad")
_HAS_PYDUB = _is_installed("pydub")

# Exception base classes for isinstance() checks in excepts.py
if not _HAS_TENACITY:
    _m = MagicMock()
    _m.RetryError = type("RetryError", (Exception,), {})
    sys.modules["tenacity"] = _m

if not _HAS_OPENAI:
    _m = MagicMock()
    for _n in ("AuthenticationError", "PermissionDeniedError", "NotFoundError",
               "BadRequestError", "RateLimitError", "APIConnectionError",
               "APIError", "ContentFilterFinishReasonError", "InternalServerError",
               "LengthFinishReasonError", "UnprocessableEntityError"):
        setattr(_m, _n, type(_n, (Exception,), {}))
    sys.modules["openai"] = _m

def _make_pkg(name, attrs=None):
    """Create a mock package that supports subpackage imports."""
    import types
    m = types.ModuleType(name)
    if attrs:
        for k, v in attrs.items():
            setattr(m, k, v)
    return m


if not _HAS_DEEPGRAM:
    # Full subpackage chain for: from deepgram.clients.common.v1.errors import DeepgramApiError
    sys.modules["deepgram.clients.common.v1.errors"] = _make_pkg(
        "deepgram.clients.common.v1.errors",
        {"DeepgramApiError": type("DeepgramApiError", (Exception,), {})}
    )
    for _pkg in ("deepgram.clients.common.v1", "deepgram.clients.common", "deepgram.clients"):
        sys.modules[_pkg] = _make_pkg(_pkg)
    sys.modules["deepgram"] = _make_pkg("deepgram")

if not _HAS_ELEVENLABS:
    sys.modules["elevenlabs.core"] = _make_pkg(
        "elevenlabs.core",
        {"ApiError": type("ApiError_11", (Exception,), {})}
    )
    sys.modules["elevenlabs"] = _make_pkg("elevenlabs")

if not _HAS_AIOHTTP:
    _ce = MagicMock()
    _ce.ClientProxyConnectionError = type("ClientProxyConnectionError", (Exception,), {})
    sys.modules["aiohttp.client_exceptions"] = _ce
    _a = MagicMock()
    _a.client_exceptions = _ce
    sys.modules["aiohttp"] = _a

if not _HAS_HTTPCORE:
    _m = MagicMock()
    for _n in ("ConnectTimeout", "ConnectError", "ReadError"):
        setattr(_m, _n, type(_n, (Exception,), {}))
    sys.modules["httpcore"] = _m

if not _HAS_HTTPX:
    _m = MagicMock()
    for _n in ("ProxyError", "ConnectError", "ConnectTimeout", "ReadError",
               "InvalidURL", "LocalProtocolError", "ProtocolError",
               "TooManyRedirects", "UnsupportedProtocol"):
        setattr(_m, _n, type(_n, (Exception,), {}))
    sys.modules["httpx"] = _m

if not _HAS_HF_HUB:
    sys.modules["huggingface_hub"] = MagicMock()

if not _HAS_TENVAD:
    _m = MagicMock()
    _m.TenVad = MagicMock()
    _m.VadOptions = MagicMock()
    sys.modules["ten_vad"] = _m

if not _HAS_PYDUB:
    _m = MagicMock()
    sys.modules["pydub"] = _m
    _ms = MagicMock()
    sys.modules["pydub.playback"] = _ms

# ---------------------------------------------------------------------------
# ASGI TestClient / TestServer adapter for aiohttp.test_utils compatibility
# ---------------------------------------------------------------------------
import types
import unittest
import httpx
from aiohttp import FormData

class _AwaitableStr(str):
    def __await__(self):
        async def _coro():
            return str(self)
        return _coro().__await__()

    def __call__(self):
        return self


class _AwaitableData:
    def __init__(self, data):
        self._data = data

    def __await__(self):
        async def _coro():
            return self._data
        return _coro().__await__()

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __contains__(self, key):
        return key in self._data

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def get(self, key, default=None):
        return self._data.get(key, default) if isinstance(self._data, dict) else default


class _WrappedResponse:
    def __init__(self, resp: httpx.Response):
        self._resp = resp

    @property
    def status(self) -> int:
        return self._resp.status_code

    @property
    def status_code(self) -> int:
        return self._resp.status_code

    @property
    def headers(self):
        return self._resp.headers

    def json(self):
        try:
            return _AwaitableData(self._resp.json())
        except Exception:
            return _AwaitableData({})

    @property
    def text(self):
        return _AwaitableStr(self._resp.text)

    async def read(self):
        return self._resp.content


class _TestServer:
    __test__ = False
    def __init__(self, app):
        self.app = app


class _TestClient:
    __test__ = False
    def __init__(self, server_or_app):
        if hasattr(server_or_app, "app"):
            self.app = server_or_app.app
        else:
            self.app = server_or_app
        self._transport = httpx.ASGITransport(app=self.app)
        self._client = httpx.AsyncClient(transport=self._transport, base_url="http://test")

    async def start_server(self):
        return self

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.__aexit__(exc_type, exc_val, exc_tb)

    def _prepare_kwargs(self, kwargs):
        if "data" in kwargs:
            data = kwargs.pop("data")
            if isinstance(data, FormData):
                files = []
                data_dict = {}
                for params, headers, content in data._fields:
                    if "filename" in params:
                        raw = content.getvalue() if hasattr(content, "getvalue") else (content.read() if hasattr(content, "read") else content)
                        files.append((params["name"], (params["filename"], raw, headers.get("Content-Type"))))
                    else:
                        data_dict[params["name"]] = content
                if files:
                    kwargs["files"] = files
                if data_dict:
                    kwargs["data"] = data_dict
            elif isinstance(data, (bytes, bytearray)):
                kwargs["content"] = data
            elif isinstance(data, dict):
                kwargs["data"] = data
        return kwargs

    async def get(self, path, **kwargs):
        kwargs = self._prepare_kwargs(kwargs)
        resp = await self._client.get(path, **kwargs)
        return _WrappedResponse(resp)

    async def post(self, path, **kwargs):
        kwargs = self._prepare_kwargs(kwargs)
        resp = await self._client.post(path, **kwargs)
        return _WrappedResponse(resp)

    async def put(self, path, **kwargs):
        kwargs = self._prepare_kwargs(kwargs)
        resp = await self._client.put(path, **kwargs)
        return _WrappedResponse(resp)

    async def delete(self, path, **kwargs):
        kwargs = self._prepare_kwargs(kwargs)
        resp = await self._client.request("DELETE", path, **kwargs)
        return _WrappedResponse(resp)


class _AioHTTPTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = await self.get_application()
        self.client = _TestClient(_TestServer(self.app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()

    async def get_application(self):
        raise NotImplementedError


# Install into sys.modules so any test importing aiohttp.test_utils gets this ASGI-backed adapter
_atu = types.ModuleType("aiohttp.test_utils")
_atu.TestClient = _TestClient
_atu.TestServer = _TestServer
_atu.AioHTTPTestCase = _AioHTTPTestCase
sys.modules["aiohttp.test_utils"] = _atu
