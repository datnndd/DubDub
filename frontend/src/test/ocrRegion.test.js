import { describe, expect, it } from 'vitest';
import { dragOcrRegion, editOcrCoordinate } from '../utils/ocrRegion';

describe('adjustable OCR region', () => {
  it('draws in either direction and enforces a minimum area', () => {
    expect(dragOcrRegion(null, { x: .9, y: .9 }, { x: .2, y: .7 })).toEqual({
      left: .2, top: .7, right: .9, bottom: .9,
    });
    expect(dragOcrRegion(null, { x: .2, y: .2 }, { x: .21, y: .21 })).toBeNull();
  });

  it('moves, resizes, and edits coordinates without leaving the video', () => {
    const rect = { left: .2, top: .7, right: .8, bottom: .9 };
    const moved = dragOcrRegion(rect, { x: .3, y: .8 }, { x: 1, y: 1 }, 'move');
    expect(moved.left).toBeCloseTo(.4);
    expect(moved.top).toBeCloseTo(.8);
    expect(moved.right).toBe(1);
    expect(moved.bottom).toBe(1);
    expect(dragOcrRegion(rect, { x: .2, y: .7 }, { x: .95, y: .95 }, 'se')).toEqual({
      left: .2, top: .7, right: .95, bottom: .95,
    });
    expect(editOcrCoordinate(rect, 'left', 95).left).toBe(.78);
  });
});
