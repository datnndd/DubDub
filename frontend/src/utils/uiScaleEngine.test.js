import { beforeEach, describe, expect, it } from 'vitest';

import { applyUiScale } from './uiScaleEngine';

describe('applyUiScale', () => {
  beforeEach(() => {
    delete document.documentElement.dataset.uiScaleEngine;
  });

  it('keeps the viewport-filling CSS path in a browser', async () => {
    await expect(applyUiScale(1.15)).resolves.toBe('css');
    expect(document.documentElement.dataset.uiScaleEngine).toBe('css');
  });
});

