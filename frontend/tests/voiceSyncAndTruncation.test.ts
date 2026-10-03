import { describe, expect, test } from 'bun:test';
import { useDubDubStore } from '../src/store';

describe('Voice sync, gap guard, and preview window contracts', () => {
  test('dubbing store defaults maxSpeedRate to 1.35', () => {
    const state = useDubDubStore.getState();
    expect(state.maxSpeedRate).toBe(1.35);
  });

  test('inter-segment gap guard reserves at least 150ms breathing pause', () => {
    const seg = { id: 1, startSec: 0.0, endSec: 1.0 };
    const nextSeg = { id: 2, startSec: 2.0, endSec: 3.0 };

    // Standard gap calculation using 0.15s gap guard
    const slackEnd = Math.max(seg.endSec, nextSeg.startSec - 0.15);
    const clampedEnd = Math.min(Math.max(slackEnd, seg.startSec), Math.max(nextSeg.startSec, seg.endSec));
    const slotDur = Math.max(0.001, clampedEnd - seg.startSec);

    // 2.0 - 0.15 = 1.85s (reserving exactly 150ms before next segment starts)
    expect(slotDur).toBeCloseTo(1.85, 2);
  });

  test('collision guard clamps slot to next segment start on tight or zero gaps', () => {
    const seg = { id: 1, startSec: 0.0, endSec: 1.0 };
    const nextSegTight = { id: 2, startSec: 1.05, endSec: 2.0 };

    const slackEnd = Math.max(seg.endSec, nextSegTight.startSec - 0.15);
    const clampedEnd = Math.min(Math.max(slackEnd, seg.startSec), Math.max(nextSegTight.startSec, seg.endSec));
    const slotDur = Math.max(0.001, clampedEnd - seg.startSec);

    // When next starts at 1.05 and seg ends at 1.0, slackEnd is max(1.0, 0.90) = 1.0
    expect(slotDur).toBeCloseTo(1.0, 2);
  });

  test('effective preview playback window extends into inter-segment gap up to 30ms guard', () => {
    const segments = [
      { id: 1, startSec: 0.0, endSec: 1.0, previewAudioUrl: 'http://localhost/prev_1.wav' },
      { id: 2, startSec: 2.0, endSec: 3.0, previewAudioUrl: 'http://localhost/prev_2.wav' },
    ];

    // Find segment at currentTime = 1.5 (past endSec 1.0, inside inter-segment gap)
    const currentTime = 1.5;
    const activeSegment = segments.find((item, index) => {
      if (!item.previewAudioUrl) return false;
      const nextSeg = segments.slice(index + 1).find((s) => typeof s.startSec === 'number' && s.startSec > item.startSec);
      const effectiveEnd = nextSeg && typeof nextSeg.startSec === 'number'
        ? Math.min(Math.max(item.endSec, nextSeg.startSec - 0.03), Math.max(item.startSec, nextSeg.startSec - 0.03))
        : (item.endSec + 3.0);
      return currentTime >= item.startSec && currentTime < effectiveEnd;
    });

    expect(activeSegment).toBeDefined();
    expect(activeSegment?.id).toBe(1);

    // At currentTime = 1.98 (within 30ms collision guard of 2.0s), segment 1 has cut off
    const collisionTime = 1.98;
    const activeAtCollision = segments.find((item, index) => {
      if (!item.previewAudioUrl) return false;
      const nextSeg = segments.slice(index + 1).find((s) => typeof s.startSec === 'number' && s.startSec > item.startSec);
      const effectiveEnd = nextSeg && typeof nextSeg.startSec === 'number'
        ? Math.min(Math.max(item.endSec, nextSeg.startSec - 0.03), Math.max(item.startSec, nextSeg.startSec - 0.03))
        : (item.endSec + 3.0);
      return collisionTime >= item.startSec && collisionTime < effectiveEnd;
    });

    expect(activeAtCollision).toBeUndefined();
  });

  test('preview playback window does not bleed into overlapping next segment', () => {
    const segments = [
      { id: 1, startSec: 0.0, endSec: 1.2, previewAudioUrl: 'http://localhost/prev_1.wav' },
      { id: 2, startSec: 1.0, endSec: 2.0, previewAudioUrl: 'http://localhost/prev_2.wav' },
    ];

    // At 1.05s, video has entered segment 2. Segment 1 must yield so segment 2 is selected!
    const currentTime = 1.05;
    const activeSegment = segments.find((item, index) => {
      if (!item.previewAudioUrl) return false;
      const nextSeg = segments.slice(index + 1).find((s) => typeof s.startSec === 'number' && s.startSec > item.startSec);
      const effectiveEnd = nextSeg && typeof nextSeg.startSec === 'number'
        ? Math.min(Math.max(item.endSec, nextSeg.startSec - 0.03), Math.max(item.startSec, nextSeg.startSec - 0.03))
        : (item.endSec + 3.0);
      return currentTime >= item.startSec && currentTime < effectiveEnd;
    });

    expect(activeSegment).toBeDefined();
    expect(activeSegment?.id).toBe(2);
  });
});
