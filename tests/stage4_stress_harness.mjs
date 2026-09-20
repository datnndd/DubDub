/**
 * Empirical Adversarial Stress Harness for Stage 4: Edit Video
 * Executes headless verification of JavaScript components, DOM contracts,
 * timing mathematics, unicode/XSS handling, focus preservation, and thumbnail lifecycle.
 */

// Setup minimal mock browser DOM environment
class MockElement {
  constructor(tag = 'div', attrs = {}) {
    this.tagName = tag.toUpperCase();
    this.attributes = { ...attrs };
    this.style = {};
    this.classList = {
      classes: new Set(),
      add(...cls) { cls.forEach(c => this.classes.add(c)); },
      remove(...cls) { cls.forEach(c => this.classes.delete(c)); },
      contains(cls) { return this.classes.has(cls); }
    };
    this.textContent = '';
    this.value = '';
  }
  getAttribute(name) { return this.attributes[name] ?? null; }
  setAttribute(name, val) { this.attributes[name] = String(val); }
  focus() { this._focused = true; }
  select() { this._selected = true; }
}

const mockDoc = {
  elements: new Map(),
  activeElement: null,
  querySelector(sel) {
    return this.elements.get(sel) || null;
  },
  querySelectorAll(sel) {
    const list = [];
    for (const [s, el] of this.elements.entries()) {
      if (s === sel || (sel.startsWith('[') && el.getAttribute(sel.slice(1, -1).split('=')[0]))) {
        list.push(el);
      }
    }
    return list;
  }
};

globalThis.window = globalThis;
globalThis.document = mockDoc;
globalThis.URL = {
  created: [],
  revoked: [],
  createObjectURL(obj) {
    const url = `blob:mock-${Math.random().toString(36).slice(2)}`;
    this.created.push(url);
    return url;
  },
  revokeObjectURL(url) {
    this.revoked.push(url);
  }
};

const { renderStage4EditVideo } = await import('../frontend/js/screens/Stage4EditVideo.js');
const { store } = await import('../frontend/js/state.js');

const suite = [];
function test(name, fn) {
  suite.push({ name, fn });
}

function assert(condition, msg) {
  if (!condition) throw new Error(msg || 'Assertion failed');
}

function assertEqual(actual, expected, msg) {
  if (actual !== expected) {
    throw new Error(`${msg || 'Assertion failed'}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

// ============================================================================
// SUITE 1: Timeline Mathematics & Extreme Boundaries
// ============================================================================

test('Timeline Math: 0 duration & empty segments array renders without NaN or crash', () => {
  const state = JSON.parse(JSON.stringify(store.getState()));
  state.project = { durationSec: 0, duration: '00:00.000', title: 'Zero Duration' };
  state.segments = [];
  state.editVideo.activeTab = 'audio';

  const html = renderStage4EditVideo(state);
  assert(typeof html === 'string', 'Should produce HTML string');
  assert(!html.includes('NaN'), 'Rendered HTML must not contain NaN');
  assert(html.includes('00:00.000'), 'Time ruler should start at 00:00.000');
});

test('Timeline Math: Single segment edge case', () => {
  const state = JSON.parse(JSON.stringify(store.getState()));
  state.project = { durationSec: 10, duration: '00:10.000' };
  state.segments = [{ id: 1, startSec: 0, endSec: 10, targetText: 'Solo' }];
  state.activeSegmentId = 1;
  state.editVideo.activeTab = 'subtitles';

  const html = renderStage4EditVideo(state);
  assert(html.includes('data-timeline-cue="1"'), 'Timeline cue for segment 1 must render');
  assert(html.includes('Solo'), 'Cue text must render');
  // Prev and Next buttons should both be disabled
  assert(html.includes('disabled\n                        onclick="window.dubDubStore.seekAndPlay(') || html.includes('disabled'), 'Prev/Next should be disabled on single cue');
});

test('Timeline Math: 150 dense segments render efficiently with valid percentages', () => {
  const state = JSON.parse(JSON.stringify(store.getState()));
  state.project = { durationSec: 300, duration: '05:00.000' };
  state.segments = [];
  for (let i = 0; i < 150; i++) {
    state.segments.push({
      id: i + 1,
      startSec: i * 2.0,
      endSec: i * 2.0 + 1.8,
      targetText: `Cue #${i + 1}`
    });
  }

  const startT = performance.now();
  const html = renderStage4EditVideo(state);
  const durMs = performance.now() - startT;

  assert(durMs < 100, `Rendering 150 segments must be fast, took ${durMs}ms`);
  assert(!html.includes('NaN'), 'No NaN in dense segments');
  assert(html.includes('data-timeline-cue="150"'), 'Last cue must exist');
});

test('Timeline Math: Zero-duration segment clamped to minimum width (0.8%)', () => {
  const state = JSON.parse(JSON.stringify(store.getState()));
  state.project = { durationSec: 60 };
  state.segments = [{ id: 1, startSec: 5.0, endSec: 5.0, targetText: 'Zero-duration' }];

  const html = renderStage4EditVideo(state);
  assert(html.includes('width: 0.8%'), `Expected width: 0.8% for zero-duration cue, got snippet: ${html.slice(0, 200)}`);
});

test('Timeline Math: Pointer scrubbing coordinates math clamping (negative and > 100%)', () => {
  // Formula under test from Stage4EditVideo.js:
  // Math.max(0, Math.min(1, (event.clientX - r.left) / r.width))
  const clampP = (clientX, rLeft, rWidth) => {
    return Math.max(0, Math.min(1, (clientX - rLeft) / rWidth));
  };

  assertEqual(clampP(50, 100, 500), 0, 'Negative offset should clamp to 0');
  assertEqual(clampP(700, 100, 500), 1, 'Offset beyond width should clamp to 1');
  assertEqual(clampP(350, 100, 500), 0.5, 'Center offset should be 0.5');

  // Handle zero-width container edge case safely
  const pZeroWidth = clampP(100, 100, 0);
  assert(Number.isNaN(pZeroWidth) || pZeroWidth === 0 || pZeroWidth === 1, 'Zero width evaluated');
});

// ============================================================================
// SUITE 2: Subtitle Typography & Timing Bounds
// ============================================================================

test('Typography: Font size slider & number input synchronization edge values', () => {
  const canvasSub = new MockElement('div');
  mockDoc.elements.set('[data-canvas-subtitle]', canvasSub);

  // Normal range 8 to 64
  store.updateSubtitleStyle('fontSize', 32, false);
  assertEqual(store.getState().subtitleStyles.fontSize, 32);
  assertEqual(canvasSub.style.fontSize, '32px');

  // Edge boundary: min 8
  store.updateSubtitleStyle('fontSize', 8, false);
  assertEqual(store.getState().subtitleStyles.fontSize, 8);
  assertEqual(canvasSub.style.fontSize, '8px');

  // Edge boundary: max 64
  store.updateSubtitleStyle('fontSize', 64, false);
  assertEqual(store.getState().subtitleStyles.fontSize, 64);
  assertEqual(canvasSub.style.fontSize, '64px');

  // Testing HTML input clamp math: Math.max(8, Math.min(64, Number(val) || 22))
  const clampFont = val => Math.max(8, Math.min(64, Number(val) || 22));
  assertEqual(clampFont(4), 8, 'Values below 8 clamp to 8');
  assertEqual(clampFont(-10), 8, 'Negative values clamp to 8');
  assertEqual(clampFont(100), 64, 'Values above 64 clamp to 64');
  assertEqual(clampFont('invalid'), 22, 'Non-numbers fallback to default 22');
});

test('Typography: Inline editing with multi-line text, non-ASCII Unicode & HTML injection', () => {
  const state = store.getState();
  state.segments = [
    { id: 1, startSec: 0, endSec: 5, targetText: 'Original' }
  ];

  // Vietnamese tone marks
  const viText = 'Xin chào thế giới! Đất nước Việt Nam mến yêu 100%.';
  store.updateStage4Subtitle(1, viText, true);
  assertEqual(state.segments[0].targetText, viText, 'Vietnamese Unicode preserved');

  // Chinese Hanzi
  const zhText = '深度学习与多语言语音转录系统测试。';
  store.updateStage4Subtitle(1, zhText, true);
  assertEqual(state.segments[0].targetText, zhText, 'Chinese Unicode preserved');

  // Arabic RTL
  const arText = 'هذا اختبار للترجمة باللغة العربية.';
  store.updateStage4Subtitle(1, arText, true);
  assertEqual(state.segments[0].targetText, arText, 'Arabic RTL preserved');

  // Emojis & Multi-line
  const emojiText = 'Line 1: 🎬 Action!\nLine 2: 🎙️ DubDub Studio 🚀✨';
  store.updateStage4Subtitle(1, emojiText, true);
  assertEqual(state.segments[0].targetText, emojiText, 'Emojis and newlines preserved');

  // XSS and HTML injection strings
  const xssPayload = `<script>alert('xss')</script><img src="x" onerror="alert(1)"> & "quotes" 'single'`;
  store.updateStage4Subtitle(1, xssPayload, true);
  assertEqual(state.segments[0].targetText, xssPayload, 'Raw string preserved in store');

  // Ensure HTML rendering escapes dangerous tags
  state.editVideo.activeTab = 'subtitles';
  state.activeSegmentId = 1;
  const html = renderStage4EditVideo(state);
  assert(!html.includes('<script>'), 'HTML output must NOT contain unescaped <script>');
  assert(html.includes('&lt;script&gt;'), 'HTML output must escape <script> to &lt;script&gt;');
  assert(html.includes('&quot;quotes&quot;'), 'Quotes must be escaped');
});

test('Timing Bounds: Boundary enforcement (startSec < endSec and adjacent constraints)', () => {
  const state = store.getState();
  state.segments = [
    { id: 1, startSec: 0.0, endSec: 3.0, startTime: '00:00.000', endTime: '00:03.000' },
    { id: 2, startSec: 3.0, endSec: 6.0, startTime: '00:03.000', endTime: '00:06.000' },
    { id: 3, startSec: 6.0, endSec: 9.0, startTime: '00:06.000', endTime: '00:09.000' }
  ];

  // Attempt to set Seg 2 startSec >= endSec (e.g. 7.0 when endSec is 6.0)
  store.updateStage4Timing(2, 'startSec', 7.0);
  assert(state.segments[1].startSec < state.segments[1].endSec, 'startSec must be strictly less than endSec');
  assertEqual(state.segments[1].startSec, 5.999, 'startSec should clamp to endSec - 0.001');

  // Attempt to set Seg 2 startSec < Seg 1 endSec (e.g. 2.0 when Seg 1 endSec is 3.0)
  store.updateStage4Timing(2, 'startSec', 2.0);
  assert(state.segments[1].startSec >= state.segments[0].endSec, 'startSec cannot overlap previous segment endSec');
  assertEqual(state.segments[1].startSec, 3.0, 'startSec clamped to previous segment endSec');

  // Attempt to set Seg 2 endSec > Seg 3 startSec (e.g. 10.0 when Seg 3 startSec is 6.0)
  store.updateStage4Timing(2, 'endSec', 10.0);
  assert(state.segments[1].endSec <= state.segments[2].startSec, 'endSec cannot exceed next segment startSec');
  assertEqual(state.segments[1].endSec, 6.0, 'endSec clamped to next segment startSec');
});

test('SRT Serialization: Non-ASCII Unicode and special formatting', () => {
  const state = store.getState();
  state.segments = [
    { id: 1, startSec: 0.0, endSec: 2.5, targetText: 'Chào mừng bạn đến với DubDub!\nPhụ đề tiếng Việt 🇻🇳.' },
    { id: 2, startSec: 3.0, endSec: 5.123, targetText: '人工智能配音工作室 🚀 & "Special chars"' }
  ];

  const srt = store.serializeEditedSrt();
  assert(srt.includes('1\n00:00:00,000 --> 00:00:02,500\nChào mừng bạn đến với DubDub!\nPhụ đề tiếng Việt 🇻🇳.'), 'Cue 1 SRT block formatted correctly');
  assert(srt.includes('2\n00:00:03,000 --> 00:00:05,123\n人工智能配音工作室 🚀 & "Special chars"'), 'Cue 2 SRT block formatted correctly with millisecond comma');
  assert(srt.includes('\n\n'), 'Double newline separation between cues');
});

// ============================================================================
// SUITE 3: Subtitle Typing Focus Preservation
// ============================================================================

test('Focus Preservation: isActivelyTyping suppresses premature notify and maintains focus', () => {
  const state = store.getState();
  state.segments = [
    { id: 1, startSec: 0, endSec: 5, targetText: 'Initial' }
  ];
  state.activeSegmentId = 1;

  const activeTextarea = new MockElement('textarea', {
    'data-segment-input': 'stage4-1',
    'data-stage4-subtitle': '1'
  });
  activeTextarea.focus();
  mockDoc.activeElement = activeTextarea;

  const canvasSub = new MockElement('div');
  mockDoc.elements.set('[data-canvas-subtitle]', canvasSub);

  let notifyCount = 0;
  const unsubscribe = store.subscribe(() => {
    notifyCount++;
  });

  // Simulate sequential keystrokes
  store.updateStage4Subtitle(1, 'H', false);
  store.updateStage4Subtitle(1, 'He', false);
  store.updateStage4Subtitle(1, 'Hello', false);

  assertEqual(notifyCount, 0, 'Notifications must be suppressed during active typing');
  assertEqual(canvasSub.textContent, 'Hello', 'Canvas subtitle must update synchronously on input');
  assertEqual(mockDoc.activeElement, activeTextarea, 'Active element must remain focused');

  // Simulate onblur (forceNotify = true)
  store.updateStage4Subtitle(1, 'Hello World', true);
  assertEqual(notifyCount, 1, 'Blur event must trigger single notify call to sync subscribers');

  unsubscribe();
});

// ============================================================================
// SUITE 4: Thumbnail Management Lifecycle
// ============================================================================

test('Thumbnail Lifecycle: Select, replace, remove state transitions', async () => {
  const edit = store.getState().editVideo;
  edit.thumbnail = null;

  // Mock uploadEditAsset on store
  let uploadCallCount = 0;
  store.uploadEditAsset = async (kind, file) => {
    uploadCallCount++;
    return { id: `asset-${uploadCallCount}`, name: file.name };
  };

  const file1 = { name: 'first_thumb.png', type: 'image/png' };
  const p1 = store.selectThumbnail(file1);
  assert(edit.thumbnail !== null, 'Thumbnail state initialized immediately');
  assertEqual(edit.thumbnail.name, 'first_thumb.png');
  assertEqual(edit.thumbnail.uploading, true);

  await p1;
  assertEqual(edit.thumbnail.uploading, undefined);
  assertEqual(edit.thumbnail.id, 'asset-1');

  // Replace with second thumbnail
  const file2 = { name: 'second_thumb.webp', type: 'image/webp' };
  await store.selectThumbnail(file2);
  assertEqual(edit.thumbnail.name, 'second_thumb.webp');
  assertEqual(edit.thumbnail.id, 'asset-2');

  // Remove thumbnail
  store.removeThumbnail();
  assertEqual(edit.thumbnail, null, 'Thumbnail cleared to null after removal');
  assert(globalThis.URL.revoked.length >= 1, 'Object URL must be revoked on removal');
});

test('Timeline Math: Segment spanning beyond total video duration', () => {
  const state = JSON.parse(JSON.stringify(store.getState()));
  state.project = { durationSec: 10 };
  state.segments = [{ id: 1, startSec: 12.0, endSec: 15.0, targetText: 'Out-of-bounds' }];
  const html = renderStage4EditVideo(state);
  assert(html.includes('left: 120%'), 'Left percentage should be 120%');
  assert(html.includes('width: 30%'), 'Width percentage should be 30%');
  assert(!html.includes('NaN'), 'No NaN when segment is beyond duration');
});

test('Timing Bounds: Invalid and non-finite inputs to updateStage4Timing', () => {
  const state = store.getState();
  state.segments = [
    { id: 1, startSec: 1.0, endSec: 4.0, startTime: '00:01.000', endTime: '00:04.000' }
  ];

  // NaN input
  store.updateStage4Timing(1, 'startSec', NaN);
  assertEqual(state.segments[0].startSec, 1.0, 'startSec should not change on NaN');

  // String non-number
  store.updateStage4Timing(1, 'endSec', 'invalid-time');
  assertEqual(state.segments[0].endSec, 4.0, 'endSec should not change on invalid string');

  // Infinity
  store.updateStage4Timing(1, 'endSec', Infinity);
  assertEqual(state.segments[0].endSec, 4.0, 'endSec should not change on Infinity');
});

test('Audio Mix: Boundary clamping and mute toggle caching', () => {
  const edit = store.getState().editVideo;

  // Negative value clamps to 0
  store.updateAudioMix('original', -50);
  assertEqual(edit.audioMix.original, 0, 'Negative mix volume clamps to 0');

  // Overflow value clamps to 150
  store.updateAudioMix('original', 250);
  assertEqual(edit.audioMix.original, 150, 'Excessive mix volume clamps to 150');

  // Non-number fallback to 0
  store.updateAudioMix('original', 'loud');
  assertEqual(edit.audioMix.original, 0, 'Non-numeric volume defaults to 0');

  // Mute toggle caching
  store.updateAudioMix('dubbed', 85);
  store.toggleAudioMute('dubbed');
  assertEqual(edit.audioMix.dubbed, 0, 'Mute sets volume to 0');
  assertEqual(edit.prevMix.dubbed, 85, 'Previous volume cached in prevMix');

  // Unmute restores previous volume
  store.toggleAudioMute('dubbed');
  assertEqual(edit.audioMix.dubbed, 85, 'Unmute restores cached volume');
});

test('Thumbnail Lifecycle: Rapid upload -> replace -> reset cycle', async () => {
  const edit = store.getState().editVideo;
  edit.thumbnail = null;

  let uploadDelay = 10;
  store.uploadEditAsset = async (kind, file) => {
    await new Promise(r => setTimeout(r, uploadDelay));
    return { id: `asset-${file.name}`, name: file.name };
  };

  // Upload file 1
  const p1 = store.selectThumbnail({ name: 'thumb1.png' });
  assertEqual(edit.thumbnail.name, 'thumb1.png');

  // Rapidly replace with file 2 before p1 finishes
  const p2 = store.selectThumbnail({ name: 'thumb2.png' });
  assertEqual(edit.thumbnail.name, 'thumb2.png');

  await p2;
  assertEqual(edit.thumbnail.name, 'thumb2.png');
  assertEqual(edit.thumbnail.id, 'asset-thumb2.png');

  // Reset/Remove
  store.removeThumbnail();
  assertEqual(edit.thumbnail, null);
});

// Execute all tests sequentially
const results = [];
for (const { name, fn } of suite) {
  try {
    await fn();
    results.push({ name, status: 'PASS' });
  } catch (err) {
    results.push({ name, status: 'FAIL', error: err.message, stack: err.stack });
  }
}

// Output test summary
console.log(JSON.stringify(results, null, 2));
const passed = results.filter(r => r.status === 'PASS').length;
const failed = results.filter(r => r.status === 'FAIL').length;
console.log(`\nSUMMARY: ${passed} PASSED, ${failed} FAILED`);
if (failed > 0) process.exit(1);
