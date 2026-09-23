# DubDub — AI Video Dubbing & Translation Studio

A powerful, full-stack video translation, speech recognition, subtitle editing, and AI dubbing workstation.

---

## ✨ Key Features

- **🎬 4-Stage Synchronized Workflow**:
  1. **Prepare**: Upload media, probe audio/video metadata, select source & target languages, configure ASR & LLM translation providers.
  2. **Review Transcript**: Video player with interactive OCR bounding boxes, slide diff inspector, speaker diarization, confidence scores, and segment editor.
  3. **Voice & Dubbing**: Multi-channel voice synthesis, pace & warmth adjustments, audio stem toggles (Original vs. Dub), locked terminology glossary, and teleprompter.
  4. **Timeline & Export**: Multi-track timeline (Video, Vocals, AI Dub, BGM, Subtitles), BGM ducking, subtitle styling, inpainting overlay, and video export.
- **🎙️ Speech Recognition (ASR)**: Faster-Whisper (Local), WhisperX, OpenAI Whisper, Deepgram, Alibaba Qwen, Azure, and more.
- **🌐 LLM Translation**: DeepSeek, OpenAI ChatGPT, Anthropic Claude, Google Gemini, Ollama (Local), etc.
- **🗣️ Speech Synthesis (TTS)**: Edge-TTS (Free), OpenAI, Azure, CosyVoice, F5-TTS, ChatTTS, and more.
- **⚡ Persistence & Background Tasks**: SQLite WAL database with job queuing, SSE streaming updates, and persistent project state across sessions.

---

## 🚀 Quick Start & How to Run

### 1. Prerequisites

- **Python**: 3.10+
- **FFmpeg**: Installed and accessible in your system `PATH` (or place `ffmpeg.exe` / `ffprobe.exe` in the project root).
- **uv** (Recommended package manager):
  ```powershell
  # Windows PowerShell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- **Bun** (for frontend builds, optional if using pre-built `frontend/dist/`):
  ```powershell
  powershell -c "irm bun.sh/install.ps1 | iex"
  ```

### 2. Install Dependencies

```bash
# Sync Python dependencies
uv sync
```

### 3. Build Frontend (Optional - pre-built in `frontend/dist`)

If you modify files inside `frontend/src/`:
```bash
cd frontend
bun install
bun run build
cd ..
```

### 4. Run the Web Application

Launch the WebUI server:
```bash
uv run python webui.py
```

Once started, open your browser and navigate to:
```
http://127.0.0.1:7860
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
├── videotrans/             # Backend Python engine & API
│   ├── api/                # Aiohttp REST API routes & SSE stream handlers
│   ├── core/               # SQLite database, project store, job store, proc registry
│   ├── recognition/        # ASR engines (Faster-Whisper, Deepgram, etc.)
│   ├── translator/         # Translation engines (DeepSeek, ChatGPT, Gemini, etc.)
│   ├── tts/                # Speech synthesis providers (Edge-TTS, Azure, OpenAI, etc.)
│   └── util/               # Media probing, FFmpeg runners, audio processing
├── frontend/               # Modern React + Vite frontend
│   ├── src/
│   │   ├── screens/        # Stage 1 to Stage 4 workflow screens
│   │   ├── components/     # Header, Drawer, Video player, Timeline, etc.
│   │   └── store/          # Zustand reactive stores (project, jobs, timeline)
│   └── dist/               # Compiled production frontend assets
├── webui.py                # Web server entry point
├── cli.py                  # CLI entry point
└── pyproject.toml          # Project configuration & dependencies
```
