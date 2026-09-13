# VoiceStudio — VieNeu-TTS Engine

VieNeu-TTS ([pnnbao97/VieNeu-TTS](https://github.com/pnnbao97/VieNeu-TTS),
PyPI [`vieneu`](https://pypi.org/project/vieneu/)) is a **Vietnamese
fine-tune of NeuTTS Air** (Qwen 0.5B backbone) with **instant voice
cloning** from a short reference clip. It is the engine to pick when the
target language is **Vietnamese** and OmniVoice's Vietnamese output is not
convincing enough.

It runs in its own subprocess **and its own venv** — the same isolation
primitive as [dots.tts](dots-tts.md), [MOSS-TTS-v1.5](moss-tts-v15.md) and
[IndexTTS-2](indextts.md) — because the `vieneu` stack (GGUF/ONNX runtime +
`sea_g2p` phonemizer) must not fight the parent's pins.

> **Opt-in, and never a default.** VieNeu is selected explicitly in
> **Model Catalogue → Engines** (or `OMNIVOICE_TTS_BACKEND=vienue`). It is not
> part of the default install.

## Platform support

- **Windows / Linux / macOS.** The default `v3turbo` mode runs the CPU path
  through **ONNX Runtime — no PyTorch needed at all**; on CUDA machines it
  uses PyTorch. No MPS claim (use CPU on Apple Silicon).
- ⚠️ The upstream RAM/latency numbers circulating in the community were
  measured on NeuTTS Air, not on VieNeu — measure on your machine and file
  feedback upstream.

## Language support

| Checkpoint | Languages | License |
|---|---|---|
| `pnnbao-ump/VieNeu-TTS-v3-Turbo` (default) | **vi** | ⚠️ verify the HF card before commercial use |
| `pnnbao-ump/VieNeu-TTS` 0.5B | **vi** | **Apache-2.0** |
| `pnnbao-ump/VieNeu-TTS-v2-Turbo` | vi + en | **Apache-2.0** |
| `pnnbao-ump/VieNeu-TTS-0.3B` | vi | **CC BY-NC 4.0 — non-commercial, never ship** |
| `pnnbao-ump/VieNeu-TTS-v2` | vi + en | ⚠️ unverified — check the HF card |

The engine rejects any other language with a clear message naming the
engine and the way out (switch to OmniVoice for 600+ languages). For a
multilingual checkpoint set `OMNIVOICE_VIENEU_LANGUAGES=vi,en`.

## Install

```powershell
# Windows (from the VoiceStudio repo root)
uv venv backend/engines/vienue/.venv
uv pip install --python backend/engines/vienue/.venv/Scripts/python.exe vieneu
```

```bash
# macOS / Linux
uv venv backend/engines/vienue/.venv
uv pip install --python backend/engines/vienue/.venv/bin/python vieneu
```

Or simply select the engine — VoiceStudio auto-installs `vieneu>=3.0` from
PyPI into `backend/engines/vienue/.venv` on first use when `uv` is available.
Model weights download from HuggingFace on first synthesize (progress is
surfaced through the normal task stream).

## Install (one-click)

With the sidecar provisioner wired (Phase 2), **Model Catalogue ? Engines ?
VieNeu-TTS** offers an in-app Install button: it creates the venv at
`%APPDATA%/OmniVoice/engines/vienue/vieneu/.venv`, installs `vieneu>=3.0`
from PyPI, and points `OMNIVOICE_VIENEU_VENV` at it (persisted in prefs) ?
no restart needed. Weights still download lazily from HuggingFace on first
synthesize. The manual steps below remain the fallback.

## Voice cloning

Provide a reference clip (WAV, a few seconds is enough — the SDK cleans and
resamples it; shorter-is-better guidance from the upstream project says
~3–5 s while VoiceStudio's dub pipeline may hand it 5–15 s, which the model
accepts) and VoiceStudio handles the rest:

- **Voice tab**: upload / record a reference + its transcript → "Use as
  profile" → synthesize with the profile selected.
- **Dub**: the per-speaker / per-segment reference flow works unchanged
  (`supports_cloning` is on).
- Without a reference the engine speaks with its built-in default voice.

The `v3turbo` mode resolves the voice **from the clip alone**; the
transcript-conditional modes (`standard` / `turbo`) additionally take
`ref_text`. VoiceStudio sends the transcript either way and the sidecar
forwards it only where the active mode uses it.

## Measured performance (one machine, take as a hint)

Measured on the maintainer's Windows x64 host, **v3-Turbo CPU path (ONNX
Runtime, no torch)**, 345-character Vietnamese paragraph, no reference clip
(built-in default voice), via the real sidecar wire protocol ? 2026-08-28:

| Run | Wall | Audio produced | RTF |
|---|---|---|---|
| Cold (incl. weights load) | 67.9 s | 17.9 s | 3.80 |
| Warm #1 | 11.3 s | 17.2 s | **0.655** |
| Warm #2 | 11.3 s | 17.4 s | **0.649** |

Reading: on a CPU-only machine, Vieneu v3-Turbo synthesizes slower than
real-time (RTF ~0.65) ? fine for Voice/Brief previews, slow for long
Audiobook/Dub renders. Prefer the CUDA path (PyTorch mode) for heavy batch
work, and keep OmniVoice for 600+-language jobs. Numbers are
machine-specific; re-measure before quoting them anywhere.

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `OMNIVOICE_VIENEU_MODE` | `v3turbo` | SDK mode: `v3turbo` (48 kHz, ONNX CPU) / `standard` (GGUF) / `fast` (LMDeploy GPU) / `remote` |
| `OMNIVOICE_VIENEU_MODEL_DIR` | required | Absolute path to a preinstalled local checkpoint; automatic model downloads are disabled |
| `OMNIVOICE_VIENEU_DEVICE` | `auto` | `auto` / `cpu` / `cuda` |
| `OMNIVOICE_VIENEU_LANGUAGES` | `vi` | Comma list the engine advertises + enforces |
| `OMNIVOICE_VIENEU_VENV` | — | Use this existing venv directory instead of the package-owned one |

## License care

Only the **Apache-2.0** variants (`VieNeu-TTS` 0.5B, `v2-Turbo`) are cleared
for commercial use. The 0.3B checkpoints are **CC BY-NC 4.0** — never ship
or recommend them. The plain `v2` variant's license is unverified: check the
HuggingFace card before adding it to your install.

## Troubleshooting

- *"VieNeu-TTS venv not found"* — create the venv as shown above, or let the
  auto-bootstrap run (needs `uv` on PATH or `OMNIVOICE_BUNDLED_UV` set).
- First synthesize is slow — weights (~1–2 GB) download from HuggingFace on
  first use; progress shows in the task stream.
- Wrong language error — the engine speaks what `OMNIVOICE_VIENEU_LANGUAGES`
  says (default `vi`); switch engines for other languages.
