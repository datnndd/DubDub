import React from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import i18n from '../i18n';

import TermsReviewPanel from '../components/dub/TermsReviewPanel';
import CheckpointBanner from '../components/CheckpointBanner';

const t = i18n.t.bind(i18n);

vi.mock('../api/dub', () => ({
  dubTranslateContext: vi.fn(),
}));

import { dubTranslateContext } from '../api/dub';

const SEGS = [
  { id: 's1', text: 'Fire up the grill.' },
  { id: 's2', text: 'Chef Okonkwo tastes it.' },
];

describe('CheckpointBanner — terms stage', () => {
  it('renders the review stop with its CTA', () => {
    render(<CheckpointBanner stage="terms" count={2} onContinue={vi.fn()} />);
    expect(screen.getByText(t('checkpoint.terms_title'))).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: new RegExp(t('checkpoint.terms_cta')) }),
    ).toBeInTheDocument();
    expect(screen.getByText(t('checkpoint.terms_hint'))).toBeInTheDocument();
  });
});

describe('TermsReviewPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('drafts the brief on mount, lets the user edit it, and starts the translation with the edited brief', async () => {
    dubTranslateContext.mockResolvedValue({
      theme: 'A cooking show.',
      terms: [{ source: 'flat-top grill', target: 'plancha' }],
      fingerprint: 'fp1',
      cached: false,
    });
    const onTranslate = vi.fn();
    render(
      <TermsReviewPanel
        jobId="j1"
        targetLang="es"
        segments={SEGS}
        onTranslate={onTranslate}
        onClose={vi.fn()}
      />,
    );

    await waitFor(() => expect(dubTranslateContext).toHaveBeenCalledTimes(1));
    expect(dubTranslateContext.mock.calls[0][0]).toMatchObject({
      job_id: 'j1',
      target_lang: 'es',
    });

    const themeBox = await screen.findByDisplayValue('A cooking show.');
    fireEvent.change(themeBox, { target: { value: 'A tense kitchen rivalry.' } });
    const sourceBox = await screen.findByDisplayValue('flat-top grill');
    fireEvent.change(sourceBox, { target: { value: 'grill' } });
    expect(screen.getByText(t('terms_review.edited'))).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: t('terms_review.start_translation') }));
    await waitFor(() =>
      expect(onTranslate).toHaveBeenCalledWith({
        theme: 'A tense kitchen rivalry.',
        terms: [expect.objectContaining({ source: 'grill', target: 'plancha' })],
      }),
    );
  });

  it('re-extracts from scratch when asked, forcing past the cache', async () => {
    dubTranslateContext.mockResolvedValue({
      theme: 'A cooking show.',
      terms: [],
      cached: true,
    });
    render(
      <TermsReviewPanel
        jobId="j1"
        targetLang="es"
        segments={SEGS}
        onTranslate={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    await waitFor(() => expect(dubTranslateContext).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByTitle(t('terms_review.re_extract')));
    await waitFor(() => expect(dubTranslateContext).toHaveBeenCalledTimes(2));
    expect(dubTranslateContext.mock.calls[1][0]).toMatchObject({ force: true });
  });

  it('shows the backend error and offers translating without a brief', async () => {
    dubTranslateContext.mockRejectedValue(new Error('no provider configured'));
    const onTranslate = vi.fn();
    render(
      <TermsReviewPanel
        jobId="j1"
        targetLang="es"
        segments={SEGS}
        onTranslate={onTranslate}
        onClose={vi.fn()}
      />,
    );
    await waitFor(() => expect(screen.getByText(/no provider configured/)).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: t('terms_review.translate_without') }));
    expect(onTranslate).toHaveBeenCalledWith(null);
  });
});
