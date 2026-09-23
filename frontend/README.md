# DubDub AI Video Dubbing Studio — Frontend

A modular, component-based frontend for the **Dubbing Video** feature, implementing a consistent, synchronized 4-stage workflow inspired by modern pro video editing suites (CapCut Pro, Descript, and broadcast teleprompter decks).

---

## 🎬 Workflow Stages

| Stage | Screen Name | Description & Key Features |
| :--- | :--- | :--- |
| **01** | **Prepare Stage** | Functional media upload and backend probe, source/target language pairing, backend-owned ASR and translation engine choices, supported voice settings, validation, task submission, progress/cancellation, and output downloads. |
| **02** | **Review Transcript** | Synchronized video player with interactive OCR bounding box overlays, OCR Slide Diff Inspector for resolving conflicts between spoken audio and keynote slides, speaker diarization cues, confidence scoring, and segment splitting/editing. |
| **03** | **Voice & Dubbing** | Broadcast split deck with EN Orig / ES Dub audio stem toggles, multi-channel voice synthesis console, pace (0.8x - 1.2x) & timbre warmth faders, locked terminology glossary, and dual-track bilingual teleprompter with quick audition buttons. |
| **04** | **Edit Video Timeline** | CapCut Pro NLE Timeline Deck: 16:9 Program Out monitor with AI Lip-mesh badge, visual OCR target inpainting overlay, dual-tabbed text/font styling & BGM ducking inspector, preset text badges, and multi-track timeline (Video, Vocals, AI Dub, BGM, Subtitles). |

---

## 🧱 Component Architecture

```
frontend/
├── index.html                   # Vite entry point
├── src/
│   ├── api/                     # Backend HTTP and event clients
│   ├── components/              # Shared React components
│   ├── screens/                 # Four workflow stages
│   ├── store/                   # Shared Zustand workflow state
│   └── types/                   # Frontend domain contracts
├── tests/                       # React behavior and API contract tests
└── dist/                        # Generated production bundle
```

---

## 🔄 State Synchronization

All screens read from and write to the shared Zustand store under
`frontend/src/store`. API access is isolated under `frontend/src/api`:
- **Step Navigation**: Stepper, footer buttons, and header tabs synchronize the active stage (1 to 4).
- **Timecode & Scrubber**: Playhead timecode (`01:26.500 / 04:30.000`) and play/pause state are preserved across all screens.
- **Language & Voices**: Prepare choices are loaded from the backend and mapped
  to the shared task runner.
- **Dialogue & Cues**: Edits made in Stage 2 transcript or Stage 3 teleprompter immediately synchronize to the Stage 4 subtitle timeline track.

---

## 🚀 How to Run & Develop

Run the application WebUI server from the repository root:

```bash
cd frontend
bun install --frozen-lockfile
bun run build
cd ..
uv run webui.py
```

Open `http://127.0.0.1:7860` in your browser. During frontend development use
`bun run dev`; Vite proxies `/api` requests to the Python backend.

The Prepare flow first uploads to `POST /api/media` for server-side inspection,
then submits the returned media identifier and selected options to
`POST /api/jobs`. This prevents the browser from supplying arbitrary local
paths and lets the server validate all engine and language choices.
