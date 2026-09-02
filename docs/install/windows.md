# VoiceStudio — Install on Windows

This page is self-contained: follow it top to bottom and you'll end up with a
working VoiceStudio install on Windows 10 / 11 (x64).

## Chạy bằng source (khuyên dùng)

```powershell
git clone https://github.com/debpalash/VoiceStudio.git
cd VoiceStudio
bun install          # frontend deps (Bun >= 1.3)
uv sync              # backend deps (uv; Python 3.11)
uv run python scripts/setup.py
bun run dev          # backend :3900 + web UI :3901
```

Mở **http://localhost:3901** — không cần Rust, không cần Visual C++ Build
Tools, không cần Git Bash (bản desktop đã được gỡ bỏ).

Model tải về máy lần đầu theo từng engine; engine TTS/ASR tùy chọn
(VieNeu, IndexTTS2…) cài qua Model Catalogue → Engines.
