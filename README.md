# DubDub — AI Video Dubbing & Translation Studio

A powerful, full-stack video translation, speech recognition, subtitle editing, and AI dubbing workstation.

---

## ✨ Key Features

- **🎬 4-Stage Synchronized Workflow**:
  1. **Prepare**: Upload media, probe audio/video metadata, select source & target languages, configure ASR & LLM translation providers.
  2. **Review Transcript**: Video player with interactive OCR bounding boxes, slide diff inspector, speaker diarization, confidence scores, and segment editor.
  3. **Voice & Dubbing**: Multi-channel voice synthesis, pace & warmth adjustments, audio stem toggles (Original vs. Dub), locked terminology glossary, and teleprompter.
  4. **Timeline & Export**: Multi-track timeline (Video, Vocals, AI Dub, BGM, Subtitles), BGM ducking, subtitle styling, inpainting overlay, and video export.
- **🎙️ Speech Recognition (ASR)**: Whisper Large-v3, Deepgram, Gemini STT, Google STT, ElevenLabs, Qwen-ASR.
- **🌐 LLM / Machine Translation**: Google Translate, OpenAI ChatGPT, Google Gemini, DeepSeek.
- **🗣️ Speech Synthesis (TTS)**: VieNeu-TTS, OmniVoice (Built-in), Gemini TTS, ElevenLabs.
- **⚡ Persistence & Background Tasks**: SQLite WAL database with job queuing, SSE streaming updates, and persistent project state across sessions.

---

## 🚀 Quick Start & How to Run

### 1. Prerequisites

- **Python**: 3.10+
- **FFmpeg**: Installed and accessible in your system `PATH` (or place `ffmpeg.exe` / `ffprobe.exe` in the project root).
- **uv** (Fast Python package manager):
  ```powershell
  # Windows PowerShell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- **Bun** (Fast JavaScript/TypeScript runtime & package manager):
  ```powershell
  powershell -c "irm bun.sh/install.ps1 | iex"
  ```

### 2. Install Dependencies

```bash
# 1. Sync Python backend dependencies
uv sync

# 2. Install dependencies (root workspace & frontend)
bun install
cd frontend && bun install && cd ..
```

### 3. Run the Web Application

The application supports two running modes:

#### Option A: Development Mode (Recommended for development)

Runs both the **FastAPI backend** and **Vite frontend dev server** concurrently with hot-reloading:

```bash
bun run dev
```

- **Web UI (Hot-Reload)**: [http://localhost:3000](http://localhost:3000)
- **Backend API (FastAPI + Uvicorn)**: [http://127.0.0.1:7860](http://127.0.0.1:7860)
- **Interactive OpenAPI Documentation**: [http://127.0.0.1:7860/docs](http://127.0.0.1:7860/docs)

*(Note: Visiting `http://127.0.0.1:7860/` will automatically redirect to `http://localhost:3000` when running in dev mode).*

---

#### Option B: Production Mode (Single-Port Serving)

Compiles the React frontend into static bundles and serves everything through a single FastAPI port:

```bash
# 1. Build the frontend
bun run build

# 2. Launch the FastAPI server
uv run python webui.py
```

Once started, open your browser at:
- **Web Application**: [http://127.0.0.1:7860](http://127.0.0.1:7860)
- **OpenAPI / Swagger UI**: [http://127.0.0.1:7860/docs](http://127.0.0.1:7860/docs)

You can also customize the host and port:
```bash
uv run python webui.py --host 0.0.0.0 --port 7860
```

---

#### Option C: Docker & Docker Compose

Run pyVideoTrans containerized with persistent storage (`./data`, `./models`, `./output`, `./logs`):

**CPU Mode:**
```bash
# Start CPU container via Docker Compose
docker compose up -d

# Or build and run directly with Docker
docker build -t pyvideotrans-webui .
docker run -d -p 7860:7860 -v ./output:/app/output -v ./models:/app/models pyvideotrans-webui
```

**GPU Mode (NVIDIA CUDA 12.8):**
```bash
# Start GPU container via Docker Compose
docker compose --profile gpu up -d webui-gpu

# Or build and run directly with Docker
docker build --build-arg USE_CUDA=true -t pyvideotrans-webui:gpu .
docker run -d --gpus all -p 7860:7860 -v ./output:/app/output -v ./models:/app/models pyvideotrans-webui:gpu
```

---

## 🛠️ CLI Mode (Headless / Batch Processing)

You can also run tasks directly via the CLI:

```bash
# Audio/Video transcription to subtitles
uv run cli.py --task stt --name "./audio.wav" --model_name large-v3

# Subtitle translation
uv run cli.py --task sts --name "./subs.srt" --target_language_code en

# Text-to-Speech synthesis
uv run cli.py --task tts --name "./subs.srt" --voice_role "en-US-GuyNeural"

# Full video translation workflow
uv run cli.py --task vtv --name "./video.mp4" --source_language_code zh-cn --target_language_code en --voice_role "en-US-GuyNeural"
```

---

## 📂 Project Structure

```
├── videotrans/             # Backend Python engine & FastAPI application
│   ├── api/                # FastAPI REST API routes, OpenAPI schemas & unbuffered SSE streaming
│   ├── core/               # SQLite WAL database, project store, job store, process registry
│   ├── recognition/        # ASR engines (Whisper, Deepgram, Gemini, ElevenLabs, Qwen)
│   ├── translator/         # Translation engines (Google, DeepSeek, ChatGPT, Gemini)
│   ├── tts/                # Speech synthesis providers (VieNeu-TTS, OmniVoice, ElevenLabs, Gemini)
│   └── util/               # Media probing, FFmpeg runners, audio processing
├── frontend/               # Modern React + Vite frontend
│   ├── src/
│   │   ├── screens/        # Stage 1 to Stage 4 workflow screens
│   │   ├── components/     # Header, Drawer, Settings, Video player, Timeline
│   │   └── store/          # Zustand reactive state stores (project, jobs, settings)
│   └── dist/               # Compiled production frontend assets
├── package.json            # Root workspace scripts (bun run dev, bun run build)
├── webui.py                # FastAPI web server entry point (Uvicorn)
├── cli.py                  # CLI entry point
└── pyproject.toml          # Python project configuration & dependencies
```
