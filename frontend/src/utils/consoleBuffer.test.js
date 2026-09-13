import { beforeEach, describe, expect, it } from 'vitest';
import { clearFrontendLogs, getFrontendLogs, installConsoleCapture } from './consoleBuffer';

describe('consoleBuffer', () => {
  // installConsoleCapture() wraps console.* exactly once per page load (a
  // module-level `installed` guard) — it must NOT be re-installed or have
  // console.warn restored between tests, or later tests run against the
  // un-wrapped original. Install once; only the ring buffer resets per test.
  installConsoleCapture();

  beforeEach(() => {
    clearFrontendLogs();
  });

  it('captures an ordinary warning', () => {
    console.warn('something genuinely worth seeing');
    expect(getFrontendLogs().some((l) => l.msg.includes('something genuinely worth seeing'))).toBe(
      true,
    );
  });
});
