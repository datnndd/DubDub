# VoiceStudio

VoiceStudio is a FastAPI + React web studio for speech generation, dubbing,
translation, transcription, and burned-subtitle OCR.

## Features

- **Voice Cloning**: Zero-shot voice cloning using reference audio clips.
- **Voice Design**: Natural voice profile creation from prompt descriptions.
- **Video Dubbing**: Complete pipeline with audio extraction, transcription, translation, and replacement.
- **Batch Queue**: Process multiple generation and conversion tasks.
- **MCP Server**: Standardized tool interface for external AI workflows.
- **Local-first**: Runs locally by default without requiring cloud subscriptions.
- **GPU Auto-Detect**: Dynamic hardware acceleration detection for CUDA, MPS, and CPU.

## Supported providers

| Capability | Providers |
| --- | --- |
| TTS | OmniVoice (Python in-process), VieNeuTTS |
| ASR | Deepgram |
| Translation | Google Translate, OpenAI-compatible LLM |
| OCR | RapidOCR, PaddleOCR |

`k2-fsa/OmniVoice` is the only Hugging Face repository the application can
download. VoiceStudio has no model catalogue or token UI for arbitrary Hugging
Face models. VieNeuTTS must point to an already-installed local model directory.

Deepgram, Google Translate, and remote OpenAI-compatible endpoints are outbound
opt-in services. VoiceStudio does not send audio or text to them until the user
configures the corresponding provider and starts an operation. A missing
Deepgram key is rejected before audio is read for upload.

## Run locally

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/), Bun, and ffmpeg.

```bash
uv sync --locked
bun install --frozen-lockfile
bun run dev
```

The web UI is served by Vite during development; FastAPI listens on port 3900.
There is no Tauri/Rust desktop application or desktop installer.

## Docker

```bash
docker compose up --build
```

See [Docker deployment](docs/install/docker.md) for volumes, ports, and provider
configuration.

## Upgrading from an older release

The database and preference migration preserves voices, projects, and common
settings. Removed TTS choices become OmniVoice; removed ASR choices become
Deepgram in an unconfigured state. Migration never sends audio to Deepgram.

Old caches are not deleted automatically. After confirming you no longer need
them, remove old provider directories manually from your configured model cache;
keep `models--k2-fsa--OmniVoice`. Back up the cache first if it contains custom
or manually managed files.

## Development

Read [AGENTS.md](.harness-core/base/AGENTS.md), [CONTRIBUTING.md](CONTRIBUTING.md),
join the [Discord community](https://discord.gg/bzQavDfVV9),
and the architecture records under `docs/adr/` before changing provider or
delivery boundaries.

VoiceStudio is licensed under AGPL-3.0-only. The upstream OmniVoice model keeps
its own license terms.
