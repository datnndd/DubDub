# VoiceStudio — Install on macOS

This page is self-contained: follow it top to bottom and you'll end up with a
working VoiceStudio install on macOS (Apple Silicon).

> [!IMPORTANT]
> **Intel Macs are not supported.** The app UI installs and launches, but the
> local Python backend **cannot run**: PyTorch stopped shipping Intel-Mac
> (macOS x86_64) wheels after 2.2.x, and VoiceStudio's dependencies require a
> newer torch — so the first-run dependency install can never succeed, from
> the DMG *or* from source
> ([#889](https://github.com/debpalash/VoiceStudio/issues/889)). The app
> detects this at first launch and tells you directly instead of failing with
> a raw installer error. Your options on an Intel Mac: point the UI at a
> remote backend running on another machine (**Settings → Sharing → Remote
> backend**), or run VoiceStudio on an Apple Silicon Mac, Windows, or Linux.

## Chạy bằng source (khuyên dùng)

```bash
git clone https://github.com/debpalash/VoiceStudio.git
cd VoiceStudio
bun install          # frontend deps (Bun >= 1.3)
uv sync              # backend deps (uv; Python 3.11)
uv run python scripts/setup.py
bun run dev          # backend :3900 + web UI :3901
```

Mở **http://localhost:3901**. Apple Silicon chạy được; audio playback cần
desktop session. Model tải về máy lần đầu theo từng engine.
