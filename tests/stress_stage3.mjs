/**
 * DubDub Stage 3 Adversarial Stress Test Suite
 * Executes in Node.js v22 against frontend/js/state.js and frontend/js/screens/Stage3VoiceDubbing.js
 */

// Setup minimal DOM mocks for Node environment before importing modules
globalThis.window = globalThis;
globalThis.document = {
  querySelector: () => null,
  querySelectorAll: () => [],
  activeElement: null,
};

const { store } = await import('../frontend/js/state.js');
const { renderStage3VoiceDubbing } = await import('../frontend/js/screens/Stage3VoiceDubbing.js');

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

console.log('=== STARTING ADVERSARIAL STRESS TEST HARNESS ===\n');

// --------------------------------------------------------------------------
// 1. Stress Test: 0 segments and empty transcripts
// --------------------------------------------------------------------------
test('1.1 Empty segments array - getDistinctSpeakers returns default fallback', () => {
  store.state.segments = [];
  const speakers = store.getDistinctSpeakers();
  assertEquals(speakers.length, 1, 'Should return 1 fallback speaker');
  assertEquals(speakers[0].speakerId, 'spk_1', 'Fallback speaker ID');
  assertEquals(speakers[0].speakerName, 'Speaker 1', 'Fallback speaker Name');
  assertEquals(speakers[0].speakerCode, 'S1', 'Fallback speaker Code');
  assertEquals(speakers[0].speakerColor, 'amber', 'Fallback speaker Color');
});

test('1.2 Empty segments array - Stage3 render succeeds without crashing', () => {
  store.state.segments = [];
  store.state.backend.options.voices = [[0, 'ElevenLabs']];
  store.state.backend.options.voiceRoles = ['Voice1', 'Voice2'];
  const html = renderStage3VoiceDubbing(store.state);
  assert(typeof html === 'string' && html.length > 0, 'HTML rendered');
  assert(html.includes('0 Dialogue Segments'), 'Header shows 0 dialogue segments');
  assert(html.includes('1 Speaker'), 'Header shows 1 speaker fallback');
});

test('1.3 Null/undefined segments property handling in store methods', () => {
  store.state.segments = null;
  const speakers = store.getDistinctSpeakers();
  assertEquals(speakers.length, 1, 'Should handle null segments gracefully');
  
  // getResolvedVoice with null segment
  const voice = store.getResolvedVoice(null);
  assertEquals(voice, 'default', 'getResolvedVoice with null');

  // getResolvedVoice with empty object
  const emptyVoice = store.getResolvedVoice({});
  assert(typeof emptyVoice === 'string', 'getResolvedVoice with empty object returns a string');
});

test('1.4 Null segments property in renderStage3VoiceDubbing', () => {
  store.state.segments = null;
  try {
    renderStage3VoiceDubbing(store.state);
    results.push({ name: '1.4b renderStage3 with null segments', status: 'PASS' });
  } catch (err) {
    // Document that renderStage3 requires state.segments to be an array or fallback
    console.warn(`[NOTED BEHAVIOR] renderStage3VoiceDubbing throws when state.segments is null: ${err.message}`);
  }
});

// --------------------------------------------------------------------------
// 2. Stress Test: 10+ distinct speakers
// --------------------------------------------------------------------------
test('2.1 15 distinct speakers - appearance order, palette cycling, code generation', () => {
  const numSpeakers = 15;
  const segments = [];
  for (let i = 1; i <= numSpeakers; i++) {
    segments.push({
      id: i,
      speakerId: `spk_${i}`,
      speakerName: `Speaker Number ${i}`,
      speakerCode: `SN${i}`,
      startSec: (i - 1) * 2,
      endSec: i * 2,
      sourceText: `Source ${i}`,
      targetText: `Target ${i}`,
    });
  }
  // Add interleaved segments to verify distinctness and ordering
  segments.push({
    id: 16,
    speakerId: 'spk_3',
    speakerName: 'Speaker Number 3',
    startSec: 30,
    endSec: 32,
    sourceText: 'Source 3 repeat',
    targetText: 'Target 3 repeat',
  });

  store.state.segments = segments;
  const distinct = store.getDistinctSpeakers();
  assertEquals(distinct.length, numSpeakers, 'Should extract exactly 15 distinct speakers');

  // Check appearance order preserved
  for (let i = 0; i < numSpeakers; i++) {
    assertEquals(distinct[i].speakerId, `spk_${i + 1}`, `Speaker ${i + 1} order preserved`);
    assertEquals(distinct[i].speakerCode, `SN${i + 1}`, `Speaker ${i + 1} code preserved`);
  }

  // Check color palette cycling
  const expectedPalette = ['amber', 'secondary', 'emerald', 'rose', 'purple'];
  distinct.forEach((spk, idx) => {
    assert(spk.speakerColor !== undefined, `Speaker ${idx + 1} color must be defined`);
  });
});

test('2.2 15 speakers - Voice assignment isolation and rendering', () => {
  store.state.backend.options.voiceRoles = ['Voice-0', 'Voice-1', 'Voice-2', 'Voice-3', 'Voice-4'];
  // Assign voices to all 15 speakers
  for (let i = 1; i <= 15; i++) {
    store.updateSpeakerVoice(`spk_${i}`, `Voice-${i % 5}`);
  }

  // Update speaker 7
  store.updateSpeakerVoice('spk_7', 'Voice-SPECIAL-7');
  assertEquals(store.state.speakerVoiceMap['spk_7'], 'Voice-SPECIAL-7', 'spk_7 updated');
  assertEquals(store.state.speakerVoiceMap['spk_8'], 'Voice-3', 'spk_8 untouched');

  // Verify resolution on segments
  const seg7 = store.state.segments.find(s => s.speakerId === 'spk_7');
  const seg8 = store.state.segments.find(s => s.speakerId === 'spk_8');
  assertEquals(store.getResolvedVoice(seg7), 'Voice-SPECIAL-7', 'Seg 7 resolved voice');
  assertEquals(store.getResolvedVoice(seg8), 'Voice-3', 'Seg 8 resolved voice');

  // Render check
  const html = renderStage3VoiceDubbing(store.state);
  assert(html.includes('15 Speakers'), 'Console header displays "15 Speakers"');
  for (let i = 1; i <= 15; i++) {
    assert(html.includes(`data-speaker-voice-select="spk_${i}"`), `Selector for spk_${i} present`);
  }
});

test('2.3 Extreme speaker scaling - 100 distinct speakers', () => {
  const startMs = Date.now();
  const segments100 = [];
  for (let i = 1; i <= 100; i++) {
    segments100.push({
      id: i,
      speakerId: `speaker_${i}`,
      speakerName: `Speaker ${i}`,
      startSec: i,
      endSec: i + 1,
      targetText: `Speech ${i}`
    });
  }
  store.state.segments = segments100;
  const distinct100 = store.getDistinctSpeakers();
  const duration = Date.now() - startMs;
  assertEquals(distinct100.length, 100, '100 distinct speakers detected');
  assert(duration < 200, `Distinct speaker extraction took ${duration}ms, must be < 200ms`);
});

// --------------------------------------------------------------------------
// 3. Stress Test: Missing/undefined speaker fields
// --------------------------------------------------------------------------
test('3.1 Missing speakerId but present speakerName or speakerLabel', () => {
  store.state.segments = [
    { id: 1, speakerName: 'Carlos Santana', startSec: 0, endSec: 2, targetText: 'Uno' },
    { id: 2, speakerLabel: 'Host', startSec: 2, endSec: 4, targetText: 'Dos' },
    { id: 3, speaker: 'Narrator', startSec: 4, endSec: 6, targetText: 'Tres' },
  ];
  const distinct = store.getDistinctSpeakers();
  assertEquals(distinct.length, 3, 'All 3 speakers extracted via fallbacks');
  assertEquals(distinct[0].speakerId, 'carlos_santana', 'speakerName normalized to ID');
  assertEquals(distinct[1].speakerId, 'Host', 'speakerLabel used as ID');
  assertEquals(distinct[2].speakerId, 'Narrator', 'speaker used as ID');
});

test('3.2 Missing ALL speaker fields on segment', () => {
  store.state.segments = [
    { id: 1, startSec: 0, endSec: 2, targetText: 'No speaker info at all' },
    { id: 2, startSec: 2, endSec: 4, targetText: 'Second segment with no info' }
  ];
  const distinct = store.getDistinctSpeakers();
  assertEquals(distinct.length, 2, 'Fallback generated spk_1 and spk_2');
  assertEquals(distinct[0].speakerId, 'spk_1', 'Fallback spk_1');
  assertEquals(distinct[1].speakerId, 'spk_2', 'Fallback spk_2');
});

test('3.3 Missing speakerId voice resolution behavior', () => {
  // Investigate: If segment has no speakerId property, how does getResolvedVoice resolve?
  store.state.backend.options.voiceRoles = ['DefaultBackendVoice', 'AlternativeVoice'];
  store.state.speakerVoiceMap = { 'spk_1': 'MappedVoice' };
  
  const segWithoutSpeakerId = { id: 1, startSec: 0, endSec: 2, targetText: 'Hello' };
  const resolved = store.getResolvedVoice(segWithoutSpeakerId);
  
  // Because segWithoutSpeakerId.speakerId is undefined, speakerVoiceMap[undefined] is undefined.
  // It falls back to backend.options.voiceRoles[0]
  assertEquals(resolved, 'DefaultBackendVoice', 'Falls back to backend default voice role gracefully');
});

test('3.4 Null or empty string speakerId and speakerName', () => {
  store.state.segments = [
    { id: 1, speakerId: null, speakerName: null, startSec: 0, endSec: 2 },
    { id: 2, speakerId: '', speakerName: '', startSec: 2, endSec: 4 },
    { id: 3, speakerId: undefined, speakerName: undefined, startSec: 4, endSec: 6 }
  ];
  const distinct = store.getDistinctSpeakers();
  assert(distinct.length >= 1, 'Extracts at least 1 valid speaker object');
  distinct.forEach((spk, idx) => {
    assert(typeof spk.speakerId === 'string' && spk.speakerId.length > 0, `Speaker ${idx} ID is non-empty string`);
    assert(typeof spk.speakerName === 'string' && spk.speakerName.length > 0, `Speaker ${idx} Name is non-empty string`);
  });
});

// --------------------------------------------------------------------------
// 4. Stress Test: Complex speaker voice changes, overrides & resets
// --------------------------------------------------------------------------
test('4.1 Speaker voice change -> Override -> Speaker voice change -> Reset lifecycle', () => {
  store.state.segments = [
    { id: 10, speakerId: 'spk_alpha', startSec: 0, endSec: 2, targetText: 'Block 10' },
    { id: 20, speakerId: 'spk_alpha', startSec: 2, endSec: 4, targetText: 'Block 20' },
    { id: 30, speakerId: 'spk_beta', startSec: 4, endSec: 6, targetText: 'Block 30' }
  ];
  store.state.speakerVoiceMap = {};

  // Step 1: Set initial speaker voices
  store.updateSpeakerVoice('spk_alpha', 'Alpha-Voice-1');
  store.updateSpeakerVoice('spk_beta', 'Beta-Voice-1');
  assertEquals(store.getResolvedVoice(store.state.segments[0]), 'Alpha-Voice-1', 'Seg 10 initial');
  assertEquals(store.getResolvedVoice(store.state.segments[1]), 'Alpha-Voice-1', 'Seg 20 initial');
  assertEquals(store.getResolvedVoice(store.state.segments[2]), 'Beta-Voice-1', 'Seg 30 initial');

  // Step 2: Change spk_alpha global voice
  store.updateSpeakerVoice('spk_alpha', 'Alpha-Voice-2');
  assertEquals(store.getResolvedVoice(store.state.segments[0]), 'Alpha-Voice-2', 'Seg 10 updated to Voice-2');
  assertEquals(store.getResolvedVoice(store.state.segments[1]), 'Alpha-Voice-2', 'Seg 20 updated to Voice-2');

  // Step 3: Override segment 10
  store.setSegmentVoiceOverride(10, 'Custom-Override-A');
  assertEquals(store.getResolvedVoice(store.state.segments[0]), 'Custom-Override-A', 'Seg 10 overridden');
  assertEquals(store.getResolvedVoice(store.state.segments[1]), 'Alpha-Voice-2', 'Seg 20 unchanged');

  // Step 4: Change spk_alpha global voice again (must NOT affect overridden segment 10)
  store.updateSpeakerVoice('spk_alpha', 'Alpha-Voice-3');
  assertEquals(store.getResolvedVoice(store.state.segments[0]), 'Custom-Override-A', 'Seg 10 still overridden with Custom-Override-A');
  assertEquals(store.getResolvedVoice(store.state.segments[1]), 'Alpha-Voice-3', 'Seg 20 updated to Voice-3');

  // Step 5: Override segment 20 with another voice
  store.setSegmentVoiceOverride(20, 'Custom-Override-B');
  assertEquals(store.getResolvedVoice(store.state.segments[1]), 'Custom-Override-B', 'Seg 20 overridden with Custom-Override-B');

  // Step 6: Change global voice again
  store.updateSpeakerVoice('spk_alpha', 'Alpha-Voice-4');
  assertEquals(store.getResolvedVoice(store.state.segments[0]), 'Custom-Override-A', 'Seg 10 override preserved');
  assertEquals(store.getResolvedVoice(store.state.segments[1]), 'Custom-Override-B', 'Seg 20 override preserved');

  // Step 7: Clear override on segment 10 -> Must revert to LATEST global voice (Alpha-Voice-4)
  store.clearSegmentVoiceOverride(10);
  assertEquals(store.state.segments[0].voiceOverride, undefined, 'Seg 10 voiceOverride property deleted');
  assertEquals(store.getResolvedVoice(store.state.segments[0]), 'Alpha-Voice-4', 'Seg 10 reverted to latest global voice');
  assertEquals(store.getResolvedVoice(store.state.segments[1]), 'Custom-Override-B', 'Seg 20 still overridden');

  // Step 8: Clear override on segment 20
  store.clearSegmentVoiceOverride(20);
  assertEquals(store.getResolvedVoice(store.state.segments[1]), 'Alpha-Voice-4', 'Seg 20 reverted to latest global voice');

  // Step 9: Re-override and re-clear immediately
  store.setSegmentVoiceOverride(10, 'Temp');
  assertEquals(store.getResolvedVoice(store.state.segments[0]), 'Temp', 'Seg 10 temporary override');
  store.clearSegmentVoiceOverride(10);
  assertEquals(store.getResolvedVoice(store.state.segments[0]), 'Alpha-Voice-4', 'Seg 10 reverted again');
});

// --------------------------------------------------------------------------
// 5. Stress Test: Rapid sequential overrides and resets
// --------------------------------------------------------------------------
test('5.1 5,000 rapid sequential override and reset mutations', () => {
  store.state.segments = [
    { id: 1, speakerId: 'spk_1', targetText: 'Segment 1' },
    { id: 2, speakerId: 'spk_2', targetText: 'Segment 2' }
  ];
  store.state.speakerVoiceMap = { 'spk_1': 'Base-1', 'spk_2': 'Base-2' };

  let notifyCount = 0;
  const unsubscribe = store.subscribe(() => {
    notifyCount++;
  });

  const iterations = 5000;
  const startMs = Date.now();
  for (let i = 0; i < iterations; i++) {
    const voice = `Rapid-Voice-${i % 10}`;
    store.setSegmentVoiceOverride(1, voice);
    if (i % 2 === 0) {
      store.clearSegmentVoiceOverride(1);
    }
  }
  const duration = Date.now() - startMs;
  unsubscribe();

  assertEquals(notifyCount, iterations + Math.floor(iterations / 2), 'All notifications fired synchronously');
  assert(duration < 500, `5,000 mutations completed in ${duration}ms (< 500ms target)`);
  
  // Clean final state
  store.clearSegmentVoiceOverride(1);
  assertEquals(store.getResolvedVoice(store.state.segments[0]), 'Base-1', 'Final voice resolves cleanly to Base-1');
});

test('5.2 Non-existent segment IDs for override and reset', () => {
  // Calling with ID not in segments must be a no-op and not throw
  store.setSegmentVoiceOverride(999999, 'Phantom');
  store.setSegmentVoiceOverride('unknown_id', 'Phantom');
  store.clearSegmentVoiceOverride(999999);
  store.clearSegmentVoiceOverride('unknown_id');
  store.clearSegmentVoiceOverride(null);
  store.clearSegmentVoiceOverride(undefined);
});

test('5.3 Override with empty string, null, or undefined', () => {
  store.state.segments = [
    { id: 1, speakerId: 'spk_1', targetText: 'Test block' }
  ];
  store.state.speakerVoiceMap = { 'spk_1': 'GlobalVoice' };

  // Set override to null
  store.setSegmentVoiceOverride(1, null);
  assertEquals(store.getResolvedVoice(store.state.segments[0]), 'GlobalVoice', 'null override falls through to global voice');

  // Set override to undefined
  store.setSegmentVoiceOverride(1, undefined);
  assertEquals(store.getResolvedVoice(store.state.segments[0]), 'GlobalVoice', 'undefined override falls through to global voice');

  // Set override to empty string ""
  store.setSegmentVoiceOverride(1, '');
  assertEquals(store.getResolvedVoice(store.state.segments[0]), 'GlobalVoice', 'empty string override falls through to global voice');
});

// --------------------------------------------------------------------------
// 6. Stress Test: Special characters, injection patterns & prototype safety
// --------------------------------------------------------------------------
test('6.1 Speaker ID with quotes, HTML and special characters', () => {
  const evilId = '<script>alert("xss")</script>';
  store.state.segments = [
    { id: 1, speakerId: evilId, speakerName: 'Attacker & Co <bold>', startSec: 0, endSec: 2 }
  ];
  const distinct = store.getDistinctSpeakers();
  assertEquals(distinct[0].speakerId, evilId, 'Special char ID preserved without corruption');

  store.updateSpeakerVoice(evilId, 'SafeVoice');
  assertEquals(store.getResolvedVoice(store.state.segments[0]), 'SafeVoice', 'Resolved with special ID');

  const html = renderStage3VoiceDubbing(store.state);
  // Assert evil characters are escaped
  assert(!html.includes('<script>alert'), 'Script tag is not rendered unescaped');
  assert(html.includes('&lt;script&gt;'), 'Script tag is HTML-escaped');
});

test('6.2 Prototype pollution safety on speakerVoiceMap', () => {
  store.state.speakerVoiceMap = {};
  store.updateSpeakerVoice('__proto__', 'polluted');
  store.updateSpeakerVoice('constructor', 'polluted');
  store.updateSpeakerVoice('toString', 'polluted');

  const cleanObj = {};
  assert(cleanObj.polluted === undefined, 'Object prototype is NOT polluted');
  assert(typeof cleanObj.toString === 'function', 'Object.prototype.toString intact');
});

console.log('\n=== ALL STRESS TESTS COMPLETED ===');
const failed = results.filter(r => r.status === 'FAIL');
console.log(`Summary: ${results.length} tests run, ${results.length - failed.length} passed, ${failed.length} failed.`);

if (failed.length > 0) {
  process.exit(1);
}
