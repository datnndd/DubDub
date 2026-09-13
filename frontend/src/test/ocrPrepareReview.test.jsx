import { act, fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import OcrPrepareReview from '../components/dub/OcrPrepareReview';

describe('OCR Prepare review', () => {
  it('lets the user edit OCR text and commits the draft only on Continue', () => {
    const onContinue = vi.fn();
    render(<OcrPrepareReview videoUrl="video.mp4" segments={[
      { id: '1', start: 0, end: 1, text: 'original OCR' },
    ]} onContinue={onContinue} onRescan={vi.fn()} />);
    expect(onContinue).not.toHaveBeenCalled();
    fireEvent.change(screen.getByRole('textbox', { name: 'Cue 1' }), { target: { value: 'reviewed text' } });
    expect(onContinue).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Continue to dubbing' }));
    expect(onContinue).toHaveBeenCalledWith([
      { id: '1', start: 0, end: 1, text: 'reviewed text' },
    ]);
  });

  it('requires every OCR cue to contain text before continuing', () => {
    render(<OcrPrepareReview segments={[
      { id: '1', start: 0, end: 1, text: '   ' },
    ]} onContinue={vi.fn()} onRescan={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Continue to dubbing' })).toBeDisabled();
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('shows Replace with OCR button when rows are selected and supports select all', () => {
    render(
      <OcrPrepareReview
        segments={[
          { id: '1', start: 0, end: 2, text: 'first' },
          { id: '2', start: 2, end: 4, text: 'second' },
        ]}
        onContinue={vi.fn()}
      />,
    );

    expect(screen.queryByRole('button', { name: /Replace with OCR/i })).toBeNull();

    // Select row 1
    const row1Checkbox = screen.getByRole('checkbox', { name: 'Select row 1' });
    fireEvent.click(row1Checkbox);
    expect(screen.getByRole('button', { name: /Replace with OCR/i })).toBeInTheDocument();
    expect(screen.getByText(/1 selected/i)).toBeInTheDocument();

    // Toggle Select All
    const selectAll = screen.getByRole('checkbox', { name: 'Select All' });
    fireEvent.click(selectAll);
    expect(screen.getByText(/2 selected/i)).toBeInTheDocument();

    fireEvent.click(selectAll);
    expect(screen.queryByRole('button', { name: /Replace with OCR/i })).toBeNull();
  });

  it('replaces selected rows with OCR cues inheriting speaker id and chronological order', async () => {
    const onReplaceWithOcr = vi.fn().mockResolvedValue({
      segments: [{ start: 2.2, end: 3.8, text: 'accurate subtitle from OCR' }],
    });

    render(
      <OcrPrepareReview
        segments={[
          { id: '1', start: 0, end: 2, text: 'first', speaker_id: 'SPK_A' },
          { id: '2', start: 2, end: 4, text: 'inaccurate ASR', speaker_id: 'SPK_B' },
          { id: '3', start: 4, end: 6, text: 'third', speaker_id: 'SPK_C' },
        ]}
        onContinue={vi.fn()}
        onReplaceWithOcr={onReplaceWithOcr}
      />,
    );

    // Select row 2
    fireEvent.click(screen.getByRole('checkbox', { name: 'Select row 2' }));
    const replaceBtn = screen.getByRole('button', { name: /Replace with OCR/i });
    fireEvent.click(replaceBtn);

    // First time prompts region dialog -> click Confirm Region
    const confirmBtn = screen.getByRole('button', { name: /Confirm Region/i });
    await act(async () => {
      fireEvent.click(confirmBtn);
    });

    await vi.waitFor(() => {
      expect(onReplaceWithOcr).toHaveBeenCalledWith(
        expect.objectContaining({
          time_ranges: [[2, 4]],
          model_id: 'rapidocr',
        }),
      );
    });

    // Verify row 2 was replaced by OCR cue and retained speaker_id SPK_B
    await vi.waitFor(() => {
      expect(screen.getByDisplayValue('accurate subtitle from OCR')).toBeInTheDocument();
      expect(screen.queryByDisplayValue('inaccurate ASR')).toBeNull();
      expect(screen.getByText('SPK_B')).toBeInTheDocument();
    });
  });

  it('clears row text to empty when OCR returns 0 cues for selected range', async () => {
    const onReplaceWithOcr = vi.fn().mockResolvedValue({
      segments: [],
    });

    render(
      <OcrPrepareReview
        segments={[
          { id: '1', start: 0, end: 2, text: 'row to clear' },
        ]}
        onContinue={vi.fn()}
        onReplaceWithOcr={onReplaceWithOcr}
      />,
    );

    fireEvent.click(screen.getByRole('checkbox', { name: 'Select row 1' }));
    fireEvent.click(screen.getByRole('button', { name: /Replace with OCR/i }));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Confirm Region/i }));
    });

    await vi.waitFor(() => {
      expect(onReplaceWithOcr).toHaveBeenCalled();
    });

    // Textarea value should be cleared to blank
    await vi.waitFor(() => {
      const textarea = screen.getByRole('textbox', { name: 'Cue 1' });
      expect(textarea.value).toBe('');
    });
  });
});
