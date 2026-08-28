/**
 * AsrEngineSelector + DeepgramConfigModal tests.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import i18n from '../i18n';

const apiJson = vi.fn();
const apiFetch = vi.fn();
const apiPost = vi.fn();
vi.mock('../api/client', () => ({
  apiJson: (...a) => apiJson(...a),
  apiFetch: (...a) => apiFetch(...a),
  apiPost: (...a) => apiPost(...a),
}));

const mockSelectEngine = vi.fn();
vi.mock('../api/hooks', () => ({
  useEngines: () => ({
    data: {
      asr: {
        active: 'faster-whisper',
        backends: [
          { id: 'faster-whisper', display_name: 'Faster-Whisper', available: true },
          { id: 'deepgram-asr', display_name: 'Deepgram (Cloud API)', available: false },
        ],
      },
    },
    isLoading: false,
  }),
  useSelectEngine: () => ({
    mutateAsync: mockSelectEngine,
    isPending: false,
  }),
}));

import AsrEngineSelector from '../components/AsrEngineSelector';

function renderWithProviders(ui) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <I18nextProvider i18n={i18n}>{ui}</I18nextProvider>
    </QueryClientProvider>,
  );
}

describe('AsrEngineSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiJson.mockResolvedValue({ model: 'nova-2', has_key: false });
  });

  it('renders ASR engines list', async () => {
    renderWithProviders(<AsrEngineSelector />);
    const select = screen.getByTestId('asr-engine-select');
    expect(select).toBeInTheDocument();
    expect(select).toHaveValue('faster-whisper');
  });

  it('opens DeepgramConfigModal when switching to unconfigured Deepgram', async () => {
    renderWithProviders(<AsrEngineSelector />);
    const select = screen.getByTestId('asr-engine-select');

    fireEvent.change(select, { target: { value: 'deepgram-asr' } });

    // Modal opens automatically because Deepgram is not configured yet
    expect(await screen.findByTestId('deepgram-modal-key')).toBeInTheDocument();
  });
});
