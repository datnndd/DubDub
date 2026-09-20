# E2E Test Infra: DubDub Stage 3 Voice & Dubbing

## Test Philosophy
- Opaque-box, requirement-driven. Derives strictly from ORIGINAL_REQUEST.md.
- Methodology: Category-Partition + Boundary Value Analysis + Pairwise + Real-World Scenarios.
- Zero network reliance: tests execute offline using deterministic test doubles and fast in-memory TestClient / invariant assertions.

## Feature Inventory
| # | Feature | Source | Tier 1 | Tier 2 | Tier 3 |
|---|---------|--------|:------:|:------:|:------:|
| 1 | Dedicated TTS Provider & Voice Discovery Console | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ |
| 2 | Global Speaker-to-Voice Mapping Matrix | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ |
| 3 | Translated Dialog Blocks with Voice Overrides & Reset | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ |
| 4 | Video Preview Subtitle Overlay & Synchronized Playback | ORIGINAL_REQUEST §R4 | 5 | 5 | ✓ |

## Test Architecture
- Test Runner: `uv run pytest tests/test_stage3_voice_dubbing.py`
- Test Categories:
  1. Backend Voice Discovery Endpoint (`GET /api/voices`): providers (0..3), aliases, language filtering, invalid inputs, error handling.
  2. Speaker Matrix & State Store: distinct speaker detection, mapping updates, propagation across segments, per-block overrides, reset to default, store persistence.
  3. Frontend Component Contracts & DOM Invariants: timecode formatting (`MM:SS.mmm`), speaker badges, editable `targetText` inputs, voice selectors, override indicators, reset buttons.
  4. Video Synchronization: seek-and-play triggers, playhead HUD sync, subtitle canvas overlay rendering.
  5. Multi-Speaker Application Workflow: complete end-to-end user scenario (changing provider, mapping 2 speakers, overriding 1 block, editing text, seeking video).

## Coverage Thresholds
- Tier 1: >=5 per feature
- Tier 2: >=5 per feature (where boundaries exist)
- Tier 3: pairwise coverage of major feature interactions
- Tier 4: realistic multi-speaker dubbing application scenario
- Target: 20+ automated tests passing with `uv run pytest`.
