# VoiceStudio — Install on Linux

This page is self-contained: follow it top to bottom and you'll end up with a
working VoiceStudio install on a Debian / Ubuntu / Fedora / Arch host.

## Chạy bằng source (khuyên dùng)

```bash
git clone https://github.com/debpalash/VoiceStudio.git
cd VoiceStudio
bun install          # frontend deps (Bun >= 1.3)
uv sync              # backend deps (uv; Python 3.11)
uv run python scripts/setup.py
bun run dev          # backend :3900 + web UI :3901
```

Mở **http://localhost:3901** — app chạy hoàn toàn cục bộ; model tải về máy
lần đầu theo từng engine bạn dùng.

> Máy Linux cần desktop session cho audio playback; bản thân backend chạy
> headless được (Docker image có sẵn — xem `docs/install/docker.md`).
