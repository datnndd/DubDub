/**
 * DubDub Stage 4 Adversarial Stress Test Suite
 * Executes in Node.js v22 against frontend/js/state.js and frontend/js/screens/Stage4EditVideo.js
 */

// Setup minimal DOM mocks for Node environment before importing modules
globalThis.window = globalThis;
globalThis.URL = {
  createObjectURL: (obj) => `blob:mock/${Math.random().toString(36).slice(2)}`,
  revokeObjectURL: (url) => {},
};
globalThis.document = {
  querySelector: () => null,
  querySelectorAll: () => [],
  activeElement: null,
};

const { store } = await import('../frontend/js/state.js');
const { renderStage4EditVideo } = await import('../frontend/js/screens/Stage4EditVideo.js');

const results = [];

function test(name, fn) {
  try {
    fn();
    results.push({ name, status: 'PASS' });
    console.log(`[PASS] ${name}`);
  } catch (err) {
    results.push({ name, status: 'FAIL', error: err.message, stack: err.stack });
    console.error(`[FAIL] ${name}: ${err.message}`);
  }
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message || 'Assertion failed');
  }
}

function assertEquals(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(`${message || 'Assertion failed'} - Expected: ${expected}, Actual: ${actual}`);
  }
}

console.log('=== STARTING STAGE 4 FRONTEND ADVERSARIAL STRESS TEST HARNESS ===\n');

// --------------------------------------------------------------------------
// 1. Audio Mix Math & Extreme Values
// --------------------------------------------------------------------------
test('1.1 Audio mix boundary clamping - extreme positive values clamped to 150', () => {
  store.updateAudioMix('dubbed', 200);
  assertEquals(store.state.editVideo.audioMix.dubbed, 150, 'dubbed volume clamped to 150');

  store.updateAudioMix('original', 99999);
  assertEquals(store.state.editVideo.audioMix.original, 150, 'original volume clamped to 150');

  store.updateAudioMix('background', 150);
  assertEquals(store.state.editVideo.audioMix.background, 150, 'background volume at boundary 150');
});

test('1.2 Audio mix boundary clamping - negative and zero values clamped to 0', () => {
  store.updateAudioMix('dubbed', -50);
  assertEquals(store.state.editVideo.audioMix.dubbed, 0, 'negative volume clamped to 0');

  store.updateAudioMix('original', -0.0001);
  assertEquals(store.state.editVideo.audioMix.original, 0, 'negative fraction clamped to 0');

  store.updateAudioMix('background', 0);
  assertEquals(store.state.editVideo.audioMix.background, 0, 'zero volume remains 0');
});

test('1.3 Audio mix non-numeric inputs - NaN, string, null, undefined fallback to 0', () => {
  store.updateAudioMix('dubbed', NaN);
  assertEquals(store.state.editVideo.audioMix.dubbed, 0, 'NaN falls back to 0');

  store.updateAudioMix('original', 'not_a_number');
  assertEquals(store.state.editVideo.audioMix.original, 0, 'string falls back to 0');

  store.updateAudioMix('background', null);
  assertEquals(store.state.editVideo.audioMix.background, 0, 'null falls back to 0');

  store.updateAudioMix('dubbed', undefined);
  assertEquals(store.state.editVideo.audioMix.dubbed, 0, 'undefined falls back to 0');
});

test('1.4 Audio mix unknown source channel - ignored safely without mutation', () => {
  const mixBefore = { ...store.state.editVideo.audioMix };
  store.updateAudioMix('alien_channel', 80);
  assertEquals(store.state.editVideo.audioMix.alien_channel, undefined, 'unknown channel not added');
});

// --------------------------------------------------------------------------
// 2. Rapid Mute Toggling and Previous Mix Restoration
// --------------------------------------------------------------------------
test('2.1 Mute toggle preserves and restores customized mix level (135%)', () => {
  store.updateAudioMix('dubbed', 135);
  assertEquals(store.state.editVideo.audioMix.dubbed, 135);

  // Mute
  store.toggleAudioMute('dubbed');
  assertEquals(store.state.editVideo.audioMix.dubbed, 0, 'muted to 0');
  assertEquals(store.state.editVideo.prevMix.dubbed, 135, 'saved previous mix 135');

  // Unmute
  store.toggleAudioMute('dubbed');
  assertEquals(store.state.editVideo.audioMix.dubbed, 135, 'restored to 135');
});

test('2.2 Rapid 20x successive mute/unmute toggles maintain stability', () => {
  store.updateAudioMix('background', 75);
  for (let i = 0; i < 20; i++) {
    store.toggleAudioMute('background');
    if (i % 2 === 0) {
      assertEquals(store.state.editVideo.audioMix.background, 0, `Iteration ${i} should be muted`);
    } else {
      assertEquals(store.state.editVideo.audioMix.background, 75, `Iteration ${i} should be restored`);
    }
  }
  // At the end of 20 toggles (i=0..19), odd last step is 19 -> restored to 75
  assertEquals(store.state.editVideo.audioMix.background, 75, 'final state after 20 toggles is restored');
});

test('2.3 Unmuting when volume was already 0 restores default channel volume', () => {
  store.state.editVideo.prevMix = {};
  store.state.editVideo.audioMix.background = 0;

  store.toggleAudioMute('background');
  // background default is 35
  assertEquals(store.state.editVideo.audioMix.background, 35, 'background restored to default 35');

  store.state.editVideo.prevMix = {};
  store.state.editVideo.audioMix.dubbed = 0;
  store.toggleAudioMute('dubbed');
  assertEquals(store.state.editVideo.audioMix.dubbed, 100, 'dubbed restored to default 100');
});

// --------------------------------------------------------------------------
// 3. Subtitle Typography & Font Size Controls
// --------------------------------------------------------------------------
test('3.1 Subtitle font size update and styling defaults', () => {
  store.updateSubtitleStyle('fontSize', 32, false);
  assertEquals(store.state.subtitleStyles.fontSize, 32, 'font size updated');
  assertEquals(store.state.subtitleStyles.color, '#FFFFFF', 'default text color is white');
  assertEquals(store.state.subtitleStyles.outlineColor, '#000000', 'default outline is black');
  assertEquals(store.state.subtitleStyles.outlineWidth, 2, 'outline width is 2');
});

// --------------------------------------------------------------------------
// 4. Asset Management Lifecycle & Revocation
// --------------------------------------------------------------------------
test('4.1 Background audio removal resets state and revokes URL', () => {
  let revoked = null;
  globalThis.URL.revokeObjectURL = (url) => { revoked = url; };

  store.state.editVideo.backgroundAudio = {
    id: 'bgm-123',
    name: 'music.mp3',
    previewUrl: 'blob:mock/bgm-url',
  };

  store.removeBackgroundAudio();
  assertEquals(store.state.editVideo.backgroundAudio, null, 'bgm reset to null');
  assertEquals(revoked, 'blob:mock/bgm-url', 'previewUrl was revoked');
});

test('4.2 Thumbnail removal resets state and revokes URL', () => {
  let revoked = null;
  globalThis.URL.revokeObjectURL = (url) => { revoked = url; };

  store.state.editVideo.thumbnail = {
    id: 'thumb-456',
    name: 'cover.jpg',
    previewUrl: 'blob:mock/thumb-url',
  };

  store.removeThumbnail();
  assertEquals(store.state.editVideo.thumbnail, null, 'thumbnail reset to null');
  assertEquals(revoked, 'blob:mock/thumb-url', 'previewUrl was revoked');
});

// --------------------------------------------------------------------------
// 5. Stage 4 Screen Rendering Robustness (DOM & Escaping)
// --------------------------------------------------------------------------
test('5.1 Screen render with zero segments does not crash or divide by zero', () => {
  store.state.segments = [];
  store.state.media = { duration: 0 };
  const html = renderStage4EditVideo(store.state);
  assert(html.includes('data-stage4-studio'), 'renders studio container');
  assert(html.includes('data-timeline-track="subtitles"'), 'renders subtitles track');
});

test('5.2 Screen render with XSS attempt in subtitle text properly escapes', () => {
  store.state.segments = [
    {
      id: 1,
      startSec: 0,
      endSec: 2,
      startTime: '00:00.000',
      endTime: '00:02.000',
      targetText: '<script>alert("XSS")</script>&"\'',
    }
  ];
  store.state.media = { duration: 10 };
  store.state.editVideo.selectedCueId = 1;
  const html = renderStage4EditVideo(store.state);
  assert(!html.includes('<script>alert("XSS")</script>'), 'dangerous tags not unescaped');
  assert(html.includes('&lt;script&gt;alert(&quot;XSS&quot;)&lt;/script&gt;'), 'properly HTML encoded');
});

test('5.3 Inspector tabs switching enforces valid values', () => {
  store.setStage4InspectorTab('thumbnail');
  assertEquals(store.state.editVideo.activeTab, 'thumbnail', 'tab set to thumbnail');

  store.setStage4InspectorTab('invalid_tab');
  assertEquals(store.state.editVideo.activeTab, 'thumbnail', 'invalid tab ignored');

  store.setStage4InspectorTab('audio');
  assertEquals(store.state.editVideo.activeTab, 'audio', 'tab set to audio');
});

console.log('\n=== SUMMARY OF JAVASCRIPT STRESS TESTS ===');
const failed = results.filter(r => r.status === 'FAIL');
console.log(`Total: ${results.length}, Passed: ${results.length - failed.length}, Failed: ${failed.length}`);
if (failed.length > 0) {
  process.exit(1);
} else {
  console.log('ALL FRONTEND JS ADVERSARIAL STRESS TESTS PASSED!');
}
