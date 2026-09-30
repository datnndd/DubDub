import { describe, it, expect } from 'bun:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { PROVIDER_DOCS, getProviderDocInfo } from '../src/config/providerDocs';
import { ProviderDocLink } from '../src/components/ProviderDocLink';

describe('Provider Documentation Registry & Links', () => {
  it('resolves official documentation links for ASR providers', () => {
    const deepgramDoc = getProviderDocInfo('deepgram', 'asr');
    expect(deepgramDoc).not.toBeNull();
    expect(deepgramDoc?.docUrl).toContain('developers.deepgram.com');

    const whisperDoc = getProviderDocInfo(0, 'asr');
    expect(whisperDoc).not.toBeNull();
    expect(whisperDoc?.docUrl).toContain('platform.openai.com/docs/guides/speech-to-text');

    const funasrDoc = getProviderDocInfo('funasr');
    expect(funasrDoc).not.toBeNull();
    expect(funasrDoc?.docUrl).toContain('github.com/modelscope/FunASR');
  });

  it('resolves official documentation links for LLM Translation providers', () => {
    const openaiDoc = getProviderDocInfo('openai', 'llm');
    expect(openaiDoc?.docUrl).toContain('platform.openai.com');

    const geminiDoc = getProviderDocInfo('gemini', 'llm');
    expect(geminiDoc?.docUrl).toContain('ai.google.dev');

    const deepseekDoc = getProviderDocInfo('deepseek', 'llm');
    expect(deepseekDoc?.docUrl).toContain('api-docs.deepseek.com');

    const claudeDoc = getProviderDocInfo('claude', 'llm');
    expect(claudeDoc?.docUrl).toContain('docs.anthropic.com');

    const googleDoc = getProviderDocInfo('google', 'llm');
    expect(googleDoc?.docUrl).toContain('cloud.google.com/translate/docs');
  });

  it('resolves official documentation links for TTS providers by number and name', () => {
    // VieNeu-TTS (id 2)
    const vieneuDoc = getProviderDocInfo(2, 'tts');
    expect(vieneuDoc?.docUrl).toContain('github.com/pnn-tech/vieneu-tts');

    // OmniVoice (id 1)
    const omniDoc = getProviderDocInfo(1, 'tts');
    expect(omniDoc?.docUrl).toContain('github.com/k2-fsa/OmniVoice');

    // ElevenLabs (id 0)
    const elevenDoc = getProviderDocInfo(0, 'tts');
    expect(elevenDoc?.docUrl).toContain('elevenlabs.io');

    // Edge-TTS (id 4)
    const edgeDoc = getProviderDocInfo(4, 'tts');
    expect(edgeDoc?.docUrl).toContain('github.com/rany2/edge-tts');
  });

  it('renders ProviderDocLink with secure new-tab attributes', () => {
    const html = renderToStaticMarkup(
      <ProviderDocLink providerId="deepgram" category="asr" variant="pill" />
    );
    expect(html).toContain('href="https://developers.deepgram.com');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noopener noreferrer"');
    expect(html).toContain('Guide');
  });

  it('returns empty markup when provider is unknown', () => {
    const html = renderToStaticMarkup(
      <ProviderDocLink providerId="unknown_nonexistent_provider_xyz" />
    );
    expect(html).toBe('');
  });
});
