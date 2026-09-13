import { afterEach, describe, expect, it, vi } from 'vitest';

describe('web API base resolver', () => {
  const originalLocation = window.location;

  afterEach(() => {
    delete window.__OMNIVOICE_API_BASE__;
    Object.defineProperty(window, 'location', { configurable: true, value: originalLocation });
    vi.resetModules();
  });

  it('prefers the runtime Docker/proxy override', async () => {
    window.__OMNIVOICE_API_BASE__ = 'https://api.example.com/';
    const mod = await import('./apiBase');
    mod._setEnvOverrideForTesting('http://build.example:3900');
    expect(mod.getApiBase()).toBe('https://api.example.com');
  });

  it('uses the explicit build override', async () => {
    const mod = await import('./apiBase');
    mod._setEnvOverrideForTesting('http://10.0.0.5:3900/');
    expect(mod.getApiBase()).toBe('http://10.0.0.5:3900');
  });

  it('follows the browser host and protocol', async () => {
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { protocol: 'https:', hostname: 'studio.local' },
    });
    const { getApiBase } = await import('./apiBase');
    expect(getApiBase()).toBe('https://studio.local:3900');
  });

  it('exports the backend port', async () => {
    const { BACKEND_PORT } = await import('./apiBase');
    expect(BACKEND_PORT).toBe(3900);
  });
});
