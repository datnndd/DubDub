import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import OcrProgress from '../components/dub/OcrProgress';

describe('OCR progress display', () => {
  it('renders scanner counters, original text, and interpolated remaining time', () => {
    const { container } = render(<OcrProgress progress={{
      stage: 'ocr', percent: 50, framesDone: 8, framesTotal: 16,
      ocrCalls: 3, skippedFrames: 5, currentText: 'Hello, World!',
      etaSeconds: 60, startedAt: Date.now() - 60000,
    }} />);
    expect(screen.getByText('OCR calls: 3 · Skipped frames: 5')).toBeInTheDocument();
    expect(screen.getByTestId('ocr-live-text')).toHaveTextContent('Hello, World!');
    expect(container.textContent).not.toContain('{{');
    expect(screen.getByRole('progressbar')).toHaveAttribute('value', '50');
  });

  it.each([
    ['sampling', 'Preparing video'], ['loading', 'Loading OCR model'], ['saving', 'Saving…'],
  ])('renders a translated label for %s', (stage, label) => {
    render(<OcrProgress progress={{ stage }} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});
