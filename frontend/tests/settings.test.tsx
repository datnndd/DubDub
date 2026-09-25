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
});
