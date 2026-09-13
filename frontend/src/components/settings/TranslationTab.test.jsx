import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import React from 'react';

// Mock the zustand store: TranslationTab reads translateQuality/setter and the
// openSettingsTab deep-link action. vi.hoisted keeps the spy addressable inside
// the hoisted vi.mock factory.
const { openSettingsTab } = vi.hoisted(() => ({ openSettingsTab: vi.fn() }));
vi.mock('../../store', () => ({
  useAppStore: (selector) =>
    selector({
      translateQuality: 'fast',
      setTranslateQuality: () => {},
      openSettingsTab,
    }),
}));

import TranslationTab from './TranslationTab';

describe('TranslationTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('points to LLM Providers instead of embedding the legacy endpoint panel', () => {
    render(<TranslationTab />);
    // The legacy inline LLM endpoint panel is gone (no reachable-badge, no
    // hardcoded-English fields, no duplicate TRANSLATE_* surface).
    expect(screen.queryByTestId('llm-base-url')).toBeNull();
    expect(screen.queryByTestId('llm-api-key')).toBeNull();
    // Instead there's a one-click jump into Settings → LLM Providers.
    const cta = screen.getByTestId('translation-open-llm-providers');
    fireEvent.click(cta);
    expect(openSettingsTab).toHaveBeenCalledWith('llm-providers');
  });

  it('drops legacy translation credential inputs from this tab', () => {
    render(<TranslationTab />);
    // The LLM (TRANSLATE_*) key/base-url/model trio lives in Settings → LLM Providers
    expect(screen.queryByPlaceholderText('API key')).toBeNull();
    expect(screen.queryByPlaceholderText('https://api.openai.com/v1')).toBeNull();
    expect(screen.queryByPlaceholderText('gpt-4o')).toBeNull();
    expect(screen.queryByPlaceholderText('DeepL API key')).toBeNull();
    expect(screen.queryByPlaceholderText('Microsoft API key')).toBeNull();
  });
});
