/**
 * Model Catalogue → Engines (ASR tab) → Deepgram Cloud ASR panel tests.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import i18n from '../i18n';

const apiJson = vi.fn();
const apiFetch = vi.fn();
const apiPost = vi.fn();
vi.mock('../api/client', () => ({
  apiJson: (...a) => apiJson(...a),
  apiFetch: (...a) => apiFetch(...a),
  apiPost: (...a) => apiPost(...a),
}));

import AsrDeepgramPanel from '../components/settings/AsrDeepgramPanel';

const SERVER = { model: 'nova-2', has_key: false };

function withI18n(node) {
  return <I18nextProvider i18n={i18n}>{node}</I18nextProvider>;
}

describe('AsrDeepgramPanel', () => {
  beforeEach(() => {
    apiJson.mockReset();
    apiFetch.mockReset();
    apiPost.mockReset();
    apiJson.mockResolvedValue(SERVER);
  });

  const waitForLoad = async () => {
    await waitFor(() =>
      expect(screen.getByTestId('asr-deepgram-model')).toHaveValue(SERVER.model),
    );
  };

  it('disables Save until a field differs from the server values', async () => {
    render(withI18n(<AsrDeepgramPanel />));
    const saveBtn = await screen.findByTestId('asr-deepgram-save');
    await waitForLoad();
    expect(saveBtn).toBeDisabled();

    // Change model
    fireEvent.change(screen.getByTestId('asr-deepgram-model'), {
      target: { value: 'nova-3' },
    });
    expect(saveBtn).not.toBeDisabled();

    // Revert model
    fireEvent.change(screen.getByTestId('asr-deepgram-model'), {
      target: { value: SERVER.model },
    });
    expect(saveBtn).toBeDisabled();
  });

  it('typing an API key marks the form dirty and enables save', async () => {
    render(withI18n(<AsrDeepgramPanel />));
    const saveBtn = await screen.findByTestId('asr-deepgram-save');
    await waitForLoad();
    expect(saveBtn).toBeDisabled();

    fireEvent.change(screen.getByTestId('asr-deepgram-api-key'), {
      target: { value: 'dg-test-key-123' },
    });
    expect(saveBtn).not.toBeDisabled();
  });

  it('shows a Saved confirmation after save', async () => {
    apiFetch.mockResolvedValue({
      json: async () => ({ model: 'nova-3', has_key: true }),
    });
    render(withI18n(<AsrDeepgramPanel />));
    await screen.findByTestId('asr-deepgram-save');
    await waitForLoad();

    fireEvent.change(screen.getByTestId('asr-deepgram-model'), {
      target: { value: 'nova-3' },
    });
    fireEvent.click(screen.getByTestId('asr-deepgram-save'));

    expect(await screen.findByTestId('asr-deepgram-saved')).toHaveTextContent(
      i18n.t('models.asrDeepgramSaved'),
    );

    const [path, opts] = apiFetch.mock.calls[0];
    expect(path).toBe('/api/settings/asr-deepgram');
    expect(JSON.parse(opts.body)).toEqual({ model: 'nova-3' });
    expect(screen.getByTestId('asr-deepgram-save')).toBeDisabled();
  });

  it('notifies onSaved callback after successful save', async () => {
    const onSaved = vi.fn();
    apiFetch.mockResolvedValue({
      json: async () => ({ model: 'nova-3', has_key: false }),
    });
    render(withI18n(<AsrDeepgramPanel onSaved={onSaved} />));
    await screen.findByTestId('asr-deepgram-save');
    await waitForLoad();

    fireEvent.change(screen.getByTestId('asr-deepgram-model'), {
      target: { value: 'nova-3' },
    });
    fireEvent.click(screen.getByTestId('asr-deepgram-save'));
    await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
  });

  it('Test connection POSTs /test and renders success latency', async () => {
    apiJson.mockResolvedValue({ model: 'nova-2', has_key: true });
    apiPost.mockResolvedValue({
      ok: true,
      status: 'ok',
      latency_ms: 55.4,
      http_status: 200,
    });
    render(withI18n(<AsrDeepgramPanel />));
    await screen.findByTestId('asr-deepgram-test');
    await waitFor(() => expect(screen.getByTestId('asr-deepgram-test')).not.toBeDisabled());

    fireEvent.click(screen.getByTestId('asr-deepgram-test'));
    const result = await screen.findByTestId('asr-deepgram-test-result');
    expect(result).toHaveTextContent(
      i18n.t('models.asrDeepgramTestOk', { ms: 55 }),
    );
    expect(apiPost).toHaveBeenCalledWith('/api/settings/asr-deepgram/test');
  });
});
