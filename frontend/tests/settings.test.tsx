import { beforeEach, describe, expect, test } from 'bun:test';
import { renderToStaticMarkup } from 'react-dom/server';

import { useDubDubStore } from '../src/store';
import { Header } from '../src/components/Header';
import { SettingsModal } from '../src/components/settings/SettingsModal';

describe('Settings Modal & Store integration', () => {
  beforeEach(() => {
    useDubDubStore.setState({
      isSettingsOpen: false,
      settingsActiveTab: 'providers',
      settingsTargetProvider: null,
    });
  });

  test('Settings slice defaults and transitions', () => {
    const store = useDubDubStore.getState();
    expect(store.isSettingsOpen).toBe(false);
    expect(store.settingsActiveTab).toBe('providers');

    store.openSettings('storage', 'deepgram');
    const updated = useDubDubStore.getState();
    expect(updated.isSettingsOpen).toBe(true);
    expect(updated.settingsActiveTab).toBe('storage');
    expect(updated.settingsTargetProvider).toBe('deepgram');

    store.setSettingsOpen(false);
    expect(useDubDubStore.getState().isSettingsOpen).toBe(false);
  });

  test('Header renders Settings button trigger', () => {
    const markup = renderToStaticMarkup(<Header />);
    expect(markup).toContain('Settings');
    expect(markup).toContain('Open Settings &amp; Preferences');
  });

  test('SettingsModal renders when isOpen is true', () => {
    const markup = renderToStaticMarkup(<SettingsModal forceOpen={true} />);
    expect(markup).toContain('Settings &amp; Preferences');
    expect(markup).toContain('API Providers');
    expect(markup).toContain('Storage &amp; Paths');
    expect(markup).toContain('General Settings');
  });

  test('SettingsModal renders nothing when isOpen is false', () => {
    const markup = renderToStaticMarkup(<SettingsModal forceOpen={false} />);
    expect(markup).toBe('');
  });

  test('initializeBackend populates options and preserves user selections when ready', async () => {
    const originalFetch = globalThis.fetch;
    try {
      globalThis.fetch = async (url: string | URL | Request) => {
        const urlStr = String(url);
        if (urlStr.includes('/api/options')) {
          return new Response(
            JSON.stringify({
              languages: [{ code: 'en', name: 'English' }, { code: 'vi', name: 'Vietnamese' }],
              asrProviders: [
                { id: 'deepgram', label: 'Deepgram', recognType: 1, models: ['nova-3', 'nova-2'], requiresSettings: true, configured: true },
                { id: 'qwen-asr', label: 'Qwen-ASR', recognType: 0, models: ['1.7B'], requiresSettings: false, configured: true },
              ],
              translationProviders: [
                { id: 'google', label: 'Google Translate', translateType: 0, requiresSettings: false, configured: true },
                { id: 'openai', label: 'OpenAI ChatGPT', translateType: 1, requiresSettings: true, configured: true, model: 'gpt-4o' },
              ],
              translationModes: [{ id: 'line', label: 'Line-by-line', description: 'Plain text' }],
              voices: [[0, 'Default Voice']],
              defaults: {
                sourceLanguage: 'en',
                targetLanguage: 'vi',
                recognType: 1,
                modelName: 'nova-3',
                translateType: 0,
                translationMode: 'line',
              },
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          );
        }
        return new Response(JSON.stringify({}), { status: 200 });
      };

      // Set user's custom selection before initializeBackend
      useDubDubStore.setState({
        backend: {
          ready: true,
          error: null,
          mediaId: null,
          status: 'idle',
          message: '',
          options: {
            languages: [],
            asrProviders: [{ id: 'deepgram', label: 'Deepgram', recognType: 1, models: ['nova-3'], requiresSettings: true, configured: false }],
            translationProviders: [],
            translationModes: [],
            voices: [],
          },
          config: {
            recognType: 1,
            translateType: 0,
            translationMode: 'srt',
            ttsType: 2,
            modelName: 'nova-2', // user selected nova-2
            voiceRole: '',
            useCuda: false,
          },
        },
      });

      await useDubDubStore.getState().initializeBackend();

      const state = useDubDubStore.getState();
      expect(state.backend.ready).toBe(true);
      // Configured should now be true
      const dg = state.backend.options.asrProviders.find((p: any) => p.id === 'deepgram');
      expect(dg?.configured).toBe(true);
      // User's custom model selection should be preserved because ready was true
      expect(state.backend.config.modelName).toBe('nova-2');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('ApiProvidersTab renders Load Models button and fetchProviderModels queries models endpoint', async () => {
    const { ApiProvidersTab } = await import('../src/components/settings/tabs/ApiProvidersTab');
    const { fetchProviderModels } = await import('../src/api/settingsApi');

    const sampleProviders = {
      openai: {
        id: 'openai',
        name: 'OpenAI ChatGPT',
        category: 'llm',
        configured: true,
        fromEnv: false,
        model: 'gpt-4o',
        models: ['gpt-4o', 'gpt-4o-mini'],
        baseUrl: '',
      },
    };

    const markup = renderToStaticMarkup(
      <ApiProvidersTab providers={sampleProviders} onRefresh={async () => {}} />
    );
    expect(markup).toContain('Load Models');
    expect(markup).toContain('gpt-4o');
    expect(markup).toContain('gpt-4o-mini');

    const originalFetch = globalThis.fetch;
    try {
      let requestedUrl = '';
      let requestedMethod = '';
      let requestedBody = '';

      globalThis.fetch = async (url: string | URL | Request, init?: RequestInit) => {
        requestedUrl = String(url);
        requestedMethod = init?.method || 'GET';
        requestedBody = String(init?.body || '');
        return new Response(
          JSON.stringify({
            ok: true,
            providerId: 'openai',
            models: ['gpt-4o', 'gpt-4o-mini', 'o1-mini'],
            message: 'Found 3 models',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      };

      const result = await fetchProviderModels('llm', 'openai', { apiKey: 'sk-test' });
      expect(result.ok).toBe(true);
      expect(requestedUrl).toBe('/api/settings/providers/llm/openai/models');
      expect(requestedMethod).toBe('POST');
      expect(JSON.parse(requestedBody)).toEqual({ apiKey: 'sk-test' });
      expect(result.models).toEqual(['gpt-4o', 'gpt-4o-mini', 'o1-mini']);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});

