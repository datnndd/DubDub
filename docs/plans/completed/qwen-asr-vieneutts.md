# Qwen-ASR and VieNeuTTS

## Outcome

Make local Qwen-ASR load its compatible Transformers implementation. Add VieNeuTTS provider, custom voice management UI, and WebUI voice controls without changing existing persisted TTS IDs.

## Context

- `qwen-asr-pvt` is installed, but imports the incompatible `transformers` 5.3.0 module.
- Qwen-ASR model folders are absent; current adapter downloads models on first use.
- VieNeuTTS has no provider, dependency, or UI in this checkout.
- A local prior implementation provides a reference for VieNeuTTS behavior.

## Approach

1. Load `transformers4576` under the module name Qwen-ASR expects before importing `qwen_asr`.
2. Add VieNeuTTS at a new TTS ID after existing IDs.
3. Add custom voice storage, desktop dialog, desktop button, and WebUI add/remove controls.
4. Add focused tests for both integrations.

## Risks and Recovery

- Do not download Qwen models during tests; validate import only.
- Preserve current TTS IDs by appending the new provider.
- Revert this change set to remove the integration and stored custom voice metadata remains inert.

## Progress

- [x] Inspect dependencies and local reference implementation.
- [x] Implement Qwen-ASR compatibility.
- [x] Implement VieNeuTTS provider and UIs.
- [x] Run focused validation.

## Validation

- Qwen-ASR compatibility import test.
- VieNeu custom voice validation and provider tests.
- Desktop/WebUI wiring tests.
