import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import EngineCompatibilityMatrix from '../components/EngineCompatibilityMatrix';

describe('EngineCompatibilityMatrix', () => {
  const sampleSharedEngines = {
    isLoading: false,
    error: null,
    data: {
      tts: {
        active: 'omnivoice',
        backends: [
          {
            id: 'omnivoice',
            display_name: 'OmniVoice',
            available: true,
          },
          {
            id: 'vienue',
            display_name: 'VieNeuTTS',
            available: true,
          },
          {
            id: 'custom_tts',
            display_name: 'Custom TTS',
            available: false,
            reason: 'Model weights not found',
          },
        ],
      },
      asr: {
        active: 'deepgram-asr',
        backends: [
          {
            id: 'deepgram-asr',
            display_name: 'Deepgram ASR',
            available: true,
          },
        ],
      },
    },
  };

  it('renders family tabs and highlights the active family', () => {
    const onFamilyChange = vi.fn();
    render(
      <EngineCompatibilityMatrix
        family="tts"
        sharedEngines={sampleSharedEngines}
        onFamilyChange={onFamilyChange}
      />,
    );

    expect(screen.getByTestId('engine-provider-picker')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'TTS' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'ASR' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'LLM' })).toBeInTheDocument();

    const asrTab = screen.getByRole('tab', { name: 'ASR' });
    fireEvent.pointerDown(asrTab, { button: 0, ctrlKey: false, pointerType: 'mouse' });
    fireEvent.mouseDown(asrTab, { button: 0 });
    fireEvent.click(asrTab);
    expect(onFamilyChange).toHaveBeenCalledWith('asr');
  });

  it('renders engine rows with active, available, and unavailable badges', () => {
    render(
      <EngineCompatibilityMatrix
        family="tts"
        sharedEngines={sampleSharedEngines}
      />,
    );

    expect(screen.getByText('OmniVoice')).toBeInTheDocument();
    expect(screen.getByText('VieNeuTTS')).toBeInTheDocument();
    expect(screen.getByText('Custom TTS')).toBeInTheDocument();
    expect(screen.getByText('Model weights not found')).toBeInTheDocument();

    const activeRow = screen.getByTestId('engine-omnivoice');
    expect(activeRow).toHaveTextContent(/Active|active/i);

    const availableRow = screen.getByTestId('engine-vienue');
    expect(availableRow).toHaveTextContent(/Available|available/i);

    const unavailableRow = screen.getByTestId('engine-custom_tts');
    expect(unavailableRow).toHaveTextContent(/Unavailable|unavailable/i);
  });

  it('calls onSelect when clicking Use on an available inactive engine', () => {
    const onSelect = vi.fn();
    render(
      <EngineCompatibilityMatrix
        family="tts"
        sharedEngines={sampleSharedEngines}
        onSelect={onSelect}
      />,
    );

    const useButtons = screen.getAllByRole('button', { name: /Use/i });
    expect(useButtons).toHaveLength(1);

    fireEvent.click(useButtons[0]);
    expect(onSelect).toHaveBeenCalledWith('tts', 'vienue');
  });

  it('renders loading indicator when sharedEngines is loading', () => {
    render(
      <EngineCompatibilityMatrix
        family="tts"
        sharedEngines={{ isLoading: true, data: {} }}
      />,
    );
    expect(screen.getByText(/Loading|loading/i)).toBeInTheDocument();
  });

  it('renders error message when sharedEngines has an error', () => {
    render(
      <EngineCompatibilityMatrix
        family="tts"
        sharedEngines={{ isLoading: false, error: new Error('Failed to fetch engines'), data: {} }}
      />,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Failed to fetch engines');
  });
});
