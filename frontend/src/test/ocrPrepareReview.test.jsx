import { fireEvent, render, screen } from '@testing-library/react';
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
});
