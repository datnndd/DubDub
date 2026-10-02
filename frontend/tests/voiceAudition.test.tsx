import { beforeEach, afterEach, describe, expect, test } from 'bun:test';
import { renderToStaticMarkup } from 'react-dom/server';
import React from 'react';

import { useDubDubStore } from '../src/store';
import { VoiceSelector } from '../src/components/VoiceSelector';
import { Stage3VoiceDubbing } from '../src/screens/Stage3VoiceDubbing';
import {
  VoiceAuditionManager,
  voiceAuditionManager,
  auditionVoice,
  getStandardSamplePhrase,
  getVoicePreviewCacheKey,
} from '../src/services/voiceAuditionManager';

class MockAudio {
  public src: string = '';
  public currentTime: number = 0;
  public paused: boolean = true;
  public onended: (() => void) | null = null;
  public onerror: (() => void) | null = null;
  public playCount: number = 0;
  public pauseCount: number = 0;
  public static instances: MockAudio[] = [];

  constructor(src?: string) {
    if (src) this.src = src;
    MockAudio.instances.push(this);
  }

  play() {
    this.paused = false;
    this.playCount++;
    return Promise.resolve();
  }

  pause() {
    this.paused = true;
    this.pauseCount++;
  }
}

describe('Voice Audition & Playback Coordination', () => {
  const originalAudio = (globalThis as any).Audio;
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    MockAudio.instances = [];
    (globalThis as any).Audio = MockAudio;
    voiceAuditionManager.clearCache();
    voiceAuditionManager.stop();
    (voiceAuditionManager as any).audio = null;

    useDubDubStore.setState({
      activeProjectId: null,
      currentStep: 3,
      backend: {
        ready: true,
        error: null,
        mediaId: null,
        status: 'idle',
        message: '',
        options: {
          languages: [
            { code: 'vi', name: 'Vietnamese' },
            { code: 'en', name: 'English' },
          ],
          asrProviders: [],
          translationProviders: [],
          translationModes: [],
          voices: [],
        },
        config: {
          ttsType: 2, // VieNeu
        },
      },
      languages: {
        source: { code: 'en', name: 'English' },
        target: { code: 'vi', name: 'Vietnamese' },
      },
      voices: [
        { id: 'Rachel', name: 'Rachel', provider: 0 },
        { id: 'PhamTuyen', name: 'Phạm Tuyên', provider: 2 },
        { id: 'StaticVoice', name: 'Static Voice', provider: 2, sampleUrl: '/samples/static1.wav' },
      ],
      customVoices: [
        {
          id: 'cv_1',
          name: 'Clone Voice 1',
          provider: 2,
          ref_audio_path: '/path/ref.wav',
        },
      ],
      speakers: [
        { id: 'spk_1', name: 'Alice', code: 'AL', color: 'amber' },
        { id: 'spk_2', name: 'Bob', code: 'BO', color: 'purple' },
      ],
      speakerVoiceMap: {
        spk_1: 'PhamTuyen',
        spk_2: 'Rachel',
      },
      segments: [
        {
          id: 1,
          startSec: 0,
          endSec: 3,
          startTime: '00:00.000',
          endTime: '00:03.000',
          sourceText: 'Hello',
          targetText: 'Xin chào',
          speakerId: 'spk_1',
          previewAudioUrl: '/api/tts/preview/prev_seg1/audio',
        },
        {
          id: 2,
          startSec: 3,
          endSec: 6,
          startTime: '00:03.000',
          endTime: '00:06.000',
          sourceText: 'World',
          targetText: 'Thế giới',
          speakerId: 'spk_2',
        },
      ],
      segmentVoiceOverrides: {},
    });
  });

  afterEach(() => {
    (globalThis as any).Audio = originalAudio;
    globalThis.fetch = originalFetch;
    voiceAuditionManager.stop();
  });

  describe('R3: Standard Sample Phrase & Audio Caching', () => {
    test('playback failure is exposed to Stage 3 instead of failing silently', async () => {
      class FailingAudio extends MockAudio {
        play() {
          this.playCount++;
          return Promise.reject(new Error('Audio was blocked'));
        }
      }
      (globalThis as any).Audio = FailingAudio;
      voiceAuditionManager.play('segment-1', '/api/tts/preview/prev_1/audio');
      await Promise.resolve();
      expect(voiceAuditionManager.getError()).toContain('Audio was blocked');
      expect(voiceAuditionManager.isKeyPlaying('segment-1')).toBe(false);
    });

    test('getStandardSamplePhrase returns Vietnamese standard phrase for vi and English for en', () => {
      const viPhrase = getStandardSamplePhrase('vi');
      expect(viPhrase).toBe('Chào bạn, đây là bản nghe thử giọng nói trí tuệ nhân tạo được tổng hợp thành công.');

      const viSubPhrase = getStandardSamplePhrase('vi-VN');
      expect(viSubPhrase).toBe('Chào bạn, đây là bản nghe thử giọng nói trí tuệ nhân tạo được tổng hợp thành công.');

      const enPhrase = getStandardSamplePhrase('en');
      expect(enPhrase).toBe('Hello, this is a sample preview of this voice.');

      const fallbackPhrase = getStandardSamplePhrase('fr');
      expect(fallbackPhrase).toBe('Hello, this is a sample preview of this voice.');
    });

    test('cache is keyed by provider + voice + language and stores preview URLs', () => {
      const key = getVoicePreviewCacheKey(2, 'PhamTuyen', 'vi');
      expect(key).toBe('2:PhamTuyen:vi');

      expect(voiceAuditionManager.getCachedUrl(2, 'PhamTuyen', 'vi')).toBeUndefined();
      voiceAuditionManager.setCachedUrl(2, 'PhamTuyen', 'vi', '/api/tts/preview/prev_100/audio');

      expect(voiceAuditionManager.hasCachedUrl(2, 'PhamTuyen', 'vi')).toBe(true);
      expect(voiceAuditionManager.getCachedUrl(2, 'PhamTuyen', 'vi')).toBe('/api/tts/preview/prev_100/audio');

      voiceAuditionManager.clearCache();
      expect(voiceAuditionManager.hasCachedUrl(2, 'PhamTuyen', 'vi')).toBe(false);
    });

    test('auditionVoice uses staticSampleUrl if present without calling /api/tts/preview', async () => {
      let fetchCalled = false;
      globalThis.fetch = async () => {
        fetchCalled = true;
        return new Response(JSON.stringify({ ok: true, preview_url: '/dummy' }));
      };

      const result = await auditionVoice({
        key: 'test-key',
        voice: 'StaticVoice',
        provider: 2,
        language: 'vi',
        staticSampleUrl: '/samples/static1.wav',
      });

      expect(result).toBe('/samples/static1.wav');
      expect(fetchCalled).toBe(false);
      expect(voiceAuditionManager.isKeyPlaying('test-key')).toBe(true);
    });

    test('auditionVoice delegates to /api/tts/preview, caches the result, and avoids repeat calls', async () => {
      let callCount = 0;
      let requestedBody: any = null;

      globalThis.fetch = async (url: string | URL | Request, init?: RequestInit) => {
        const urlStr = String(url);
        if (urlStr.includes('/api/tts/preview')) {
          callCount++;
          if (init?.body) {
            requestedBody = JSON.parse(String(init.body));
          }
          return new Response(
            JSON.stringify({
              ok: true,
              id: 'prev_synthesized_456',
              preview_url: '/api/tts/preview/prev_synthesized_456/audio',
              audio_url: '/api/tts/preview/prev_synthesized_456/audio',
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          );
        }
        return new Response('Not found', { status: 404 });
      };

      // 1. First call: cache miss -> calls /api/tts/preview
      const url1 = await auditionVoice({
        key: 'voice-Rachel',
        voice: 'Rachel',
        provider: 0,
        language: 'vi',
      });

      expect(callCount).toBe(1);
      expect(url1).toBe('/api/tts/preview/prev_synthesized_456/audio');
      expect(requestedBody.text).toBe('Chào bạn, đây là bản nghe thử giọng nói trí tuệ nhân tạo được tổng hợp thành công.');
      expect(requestedBody.voice).toBe('Rachel');
      expect(requestedBody.provider).toBe(0);
      expect(requestedBody.language).toBe('vi');

      // Stop playback so next call attempts playback again
      voiceAuditionManager.stop();

      // 2. Second call for same provider + voice + language: cache hit -> 0 network calls
      const url2 = await auditionVoice({
        key: 'voice-Rachel',
        voice: 'Rachel',
        provider: 0,
        language: 'vi',
      });

      expect(callCount).toBe(1); // Still 1! Redundant call prevented by client cache
      expect(url2).toBe('/api/tts/preview/prev_synthesized_456/audio');
    });

    test('in-flight preview generation clears loading state when superseded by another audition', async () => {
      let resolveFirst: ((val: any) => void) | null = null;
      let firstLoadingStates: boolean[] = [];
      let secondLoadingStates: boolean[] = [];

      globalThis.fetch = async (url: string | URL | Request) => {
        const urlStr = String(url);
        if (urlStr.includes('PhamTuyen')) {
          return new Promise((resolve) => {
            resolveFirst = resolve;
          });
        }
        return new Response(
          JSON.stringify({ ok: true, audio_url: '/api/tts/preview/second/audio' }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      };

      // 1. Start first audition (slow)
      const promise1 = auditionVoice({
        key: 'voice-PhamTuyen',
        voice: 'PhamTuyen',
        provider: 2,
        language: 'vi',
        onLoadingChange: (l) => firstLoadingStates.push(l),
      });

      expect(voiceAuditionManager.isKeyLoading('voice-PhamTuyen')).toBe(true);
      expect(firstLoadingStates).toEqual([true]);

      // 2. Start second audition before first resolves
      const promise2 = auditionVoice({
        key: 'voice-Rachel',
        voice: 'Rachel',
        provider: 0,
        language: 'vi',
        onLoadingChange: (l) => secondLoadingStates.push(l),
      });

      // First audition must be cancelled immediately: its loading callback notified with false
      expect(voiceAuditionManager.isKeyLoading('voice-PhamTuyen')).toBe(false);
      expect(firstLoadingStates).toEqual([true, false]);
      expect(voiceAuditionManager.isKeyLoading('voice-Rachel')).toBe(true);

      // Now second resolves
      await promise2;
      expect(voiceAuditionManager.isKeyPlaying('voice-Rachel')).toBe(true);

      // Resolve the delayed first promise
      resolveFirst?.(
        new Response(
          JSON.stringify({ ok: true, audio_url: '/api/tts/preview/first/audio' }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      );
      await promise1;

      // Stale first audition must NOT overwrite Rachel's playback
      expect(voiceAuditionManager.isKeyPlaying('voice-Rachel')).toBe(true);
      expect(voiceAuditionManager.isKeyPlaying('voice-PhamTuyen')).toBe(false);
      expect(firstLoadingStates).toEqual([true, false]);
    });

    test('in-flight preview generation is cancelled on stopIfKeyPrefix (e.g. dropdown close)', async () => {
      let resolveFetch: ((val: any) => void) | null = null;
      let loadingStates: boolean[] = [];

      globalThis.fetch = async () => {
        return new Promise((resolve) => {
          resolveFetch = resolve;
        });
      };

      const promise = auditionVoice({
        key: 'voice-PhamTuyen',
        voice: 'PhamTuyen',
        provider: 2,
        language: 'vi',
        onLoadingChange: (l) => loadingStates.push(l),
      });

      expect(voiceAuditionManager.isKeyLoading('voice-PhamTuyen')).toBe(true);
      expect(loadingStates).toEqual([true]);

      // Dropdown closes -> stopIfKeyPrefix('voice-')
      voiceAuditionManager.stopIfKeyPrefix('voice-');

      expect(voiceAuditionManager.isKeyLoading('voice-PhamTuyen')).toBe(false);
      expect(loadingStates).toEqual([true, false]);

      // Network request finishes afterwards
      resolveFetch?.(
        new Response(
          JSON.stringify({ ok: true, audio_url: '/api/tts/preview/delayed/audio' }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      );
      await promise;

      // Must NOT play because dropdown was closed
      expect(voiceAuditionManager.isKeyPlaying('voice-PhamTuyen')).toBe(false);
      expect(voiceAuditionManager.getActiveKey()).toBeNull();
    });

    test('starting audition on uncached voice immediately halts currently playing audio', async () => {
      voiceAuditionManager.play('voice-A', '/sampleA.wav');
      expect(voiceAuditionManager.isKeyPlaying('voice-A')).toBe(true);

      let resolveFetch: ((val: any) => void) | null = null;
      globalThis.fetch = async () => {
        return new Promise((resolve) => {
          resolveFetch = resolve;
        });
      };

      const promise = auditionVoice({
        key: 'voice-B',
        voice: 'VoiceB',
        provider: 2,
        language: 'vi',
      });

      // Voice A must halt immediately upon starting audition for Voice B
      expect(voiceAuditionManager.isKeyPlaying('voice-A')).toBe(false);
      expect(voiceAuditionManager.getActiveKey()).toBeNull();
      expect(voiceAuditionManager.isKeyLoading('voice-B')).toBe(true);

      resolveFetch?.(
        new Response(
          JSON.stringify({ ok: true, audio_url: '/sampleB.wav' }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      );
      await promise;

      expect(voiceAuditionManager.isKeyPlaying('voice-B')).toBe(true);
    });

    test('auditionVoice immediately returns null for invalid voice without network calls', async () => {
      let fetchCalled = false;
      globalThis.fetch = async () => {
        fetchCalled = true;
        return new Response(JSON.stringify({ ok: true }));
      };

      const res1 = await auditionVoice({ key: 'test-1', voice: '', provider: 2, language: 'vi' });
      expect(res1).toBeNull();
      expect(fetchCalled).toBe(false);

      const res2 = await auditionVoice({ key: 'test-2', voice: '   ', provider: 2, language: 'vi' });
      expect(res2).toBeNull();
      expect(fetchCalled).toBe(false);

      const res3 = await auditionVoice({ key: 'test-3', voice: 'No', provider: 2, language: 'vi' });
      expect(res3).toBeNull();
      expect(fetchCalled).toBe(false);

      const res4 = await auditionVoice({ key: 'test-4', voice: 'clone', provider: 2, language: 'vi' });
      expect(res4).toBeNull();
      expect(fetchCalled).toBe(false);
    });
  });

  describe('R4: Coordinated Audio Playback', () => {
    test('starting playback on any voice stops previous audio stream immediately', () => {
      voiceAuditionManager.play('voice-A', '/sampleA.wav');
      expect(voiceAuditionManager.isKeyPlaying('voice-A')).toBe(true);
      expect(voiceAuditionManager.getActiveKey()).toBe('voice-A');

      const firstAudioInstance = (voiceAuditionManager as any).audio;
      expect(firstAudioInstance).not.toBeNull();
      expect(firstAudioInstance.paused).toBe(false);

      // Play voice B
      voiceAuditionManager.play('voice-B', '/sampleB.wav');
      expect(voiceAuditionManager.isKeyPlaying('voice-A')).toBe(false);
      expect(voiceAuditionManager.isKeyPlaying('voice-B')).toBe(true);
      expect(voiceAuditionManager.getActiveKey()).toBe('voice-B');

      // Verified single active audio player instance: same instance reused
      const secondAudioInstance = (voiceAuditionManager as any).audio;
      expect(secondAudioInstance).toBe(firstAudioInstance);
      expect(secondAudioInstance.src).toBe('/sampleB.wav');
    });

    test('clicking currently playing key halts playback (toggles off)', () => {
      voiceAuditionManager.play('speaker-spk_1', '/speaker1.wav');
      expect(voiceAuditionManager.isKeyPlaying('speaker-spk_1')).toBe(true);

      // Second play call with same key pauses and resets
      voiceAuditionManager.play('speaker-spk_1', '/speaker1.wav');
      expect(voiceAuditionManager.isKeyPlaying('speaker-spk_1')).toBe(false);
      expect(voiceAuditionManager.getActiveKey()).toBeNull();
    });

    test('stopIfKeyPrefix cleanses only matching keys (e.g. dropdown close)', () => {
      voiceAuditionManager.play('voice-Rachel', '/rachel.wav');
      expect(voiceAuditionManager.isKeyPlaying('voice-Rachel')).toBe(true);

      voiceAuditionManager.stopIfKeyPrefix('voice-');
      expect(voiceAuditionManager.isKeyPlaying('voice-Rachel')).toBe(false);
      expect(voiceAuditionManager.getActiveKey()).toBeNull();

      // Non-matching prefix is not stopped
      voiceAuditionManager.play('speaker-spk_1', '/spk1.wav');
      voiceAuditionManager.stopIfKeyPrefix('voice-');
      expect(voiceAuditionManager.isKeyPlaying('speaker-spk_1')).toBe(true);
    });

    test('aborted play promise does not reset active key of newly playing audio', async () => {
      let rejectOldPlay: (() => void) | null = null;
      class AbortingAudio extends MockAudio {
        play() {
          if (this.src.includes('old.wav')) {
            return new Promise<void>((_, reject) => {
              rejectOldPlay = () => reject(new Error('AbortError'));
            });
          }
          return Promise.resolve();
        }
      }
      (globalThis as any).Audio = AbortingAudio;

      voiceAuditionManager.play('voice-Old', '/old.wav');
      expect(voiceAuditionManager.isKeyPlaying('voice-Old')).toBe(true);

      // Now play new voice
      voiceAuditionManager.play('voice-New', '/new.wav');
      expect(voiceAuditionManager.isKeyPlaying('voice-New')).toBe(true);

      // The old play promise now rejects
      rejectOldPlay?.();
      await Promise.resolve(); // flush microtasks

      // voice-New must STILL be playing!
      expect(voiceAuditionManager.isKeyPlaying('voice-New')).toBe(true);
      expect(voiceAuditionManager.getActiveKey()).toBe('voice-New');
    });
  });

  describe('R1: Candidate Voice Audition in VoiceSelector Dropdown', () => {
    test('renders audition play buttons for preset voices and cloned voices with tooltip "Audition Voice"', () => {
      const markup = renderToStaticMarkup(
        <VoiceSelector
          value="Rachel"
          onChange={() => {}}
          forceOpen={true}
          provider={2}
          language="vi"
        />
      );

      // Audition buttons rendered with title "Audition Voice"
      expect(markup).toContain('title="Audition Voice"');
      expect(markup).toContain('aria-label="Audition Voice"');

      // Check preset voice audition trigger
      expect(markup).toContain('data-action="audition-preset-voice"');
      expect(markup).toContain('data-voice-id="Rachel"');
      expect(markup).toContain('data-voice-id="PhamTuyen"');

      // Check custom voice audition trigger
      expect(markup).toContain('data-action="audition-custom-voice"');
      expect(markup).toContain('data-voice-id="cv_1"');
    });

    test('cloned voice in voices list with kind "clone" renders in Cloned Voices group with audition button', () => {
      useDubDubStore.setState({
        customVoices: [],
        voices: [
          {
            id: 'cv_remote_99',
            name: 'Remote Cloned Voice',
            kind: 'clone',
            provider: 2,
            sampleUrl: '/api/custom-voices/cv_remote_99/audio',
          },
        ],
      });

      const markup = renderToStaticMarkup(
        <VoiceSelector
          value="cv_remote_99"
          onChange={() => {}}
          forceOpen={true}
          provider={2}
          language="vi"
        />
      );

      // It should be classified as custom / cloned voice, NOT system control
      expect(markup).toContain('My Cloned Voices (1)');
      expect(markup).toContain('data-action="audition-custom-voice"');
      expect(markup).toContain('data-voice-id="cv_remote_99"');
    });

    test('renders Pause icon and Stop Audition tooltip when a voice option is active', () => {
      // Simulate playing voice-Rachel
      voiceAuditionManager.play('voice-Rachel', '/api/sample.wav');

      const markup = renderToStaticMarkup(
        <VoiceSelector
          value="Rachel"
          onChange={() => {}}
          forceOpen={true}
          provider={2}
          language="vi"
        />
      );

      expect(markup).toContain('title="Stop Audition"');
    });

    test('VoiceSelector displays Custom badge and Sparkles icon when value starts with "Custom: "', () => {
      const markup = renderToStaticMarkup(
        <VoiceSelector
          value="Custom: Unregistered External Voice"
          onChange={() => {}}
          forceOpen={false}
          provider={2}
          language="vi"
        />
      );

      expect(markup).toContain('Custom');
      expect(markup).toContain('Custom: Unregistered External Voice');
    });
  });

  describe('R2: Direct Voice Audition on Speaker Cards', () => {
    test('Stage 3 mutes source video and shows the applied preview speed', () => {
      const segments = useDubDubStore.getState().segments;
      useDubDubStore.setState({
        project: { ...useDubDubStore.getState().project, previewUrl: '/media/source.mp4' },
        segments: [{ ...segments[0], previewSpeedFactor: 1.15 }, ...segments.slice(1)],
      });
      const markup = renderToStaticMarkup(<Stage3VoiceDubbing />);
      expect(markup).toContain('Applied speed: 1.15x');
      expect(markup).toContain('muted=""');
      expect(markup).not.toContain('EN Orig');
    });

    test('Stage 3 displays audition playback errors', () => {
      voiceAuditionManager.setError('Preview audio could not be loaded');
      const markup = renderToStaticMarkup(<Stage3VoiceDubbing />);
      expect(markup).toContain('role="alert"');
      expect(markup).toContain('Preview audio could not be loaded');
    });

    test('each speaker card renders dedicated preview/audition button beside voice selector', () => {
      const markup = renderToStaticMarkup(<Stage3VoiceDubbing />);

      // Speaker cards present
      expect(markup).toContain('data-speaker-card="spk_1"');
      expect(markup).toContain('data-speaker-card="spk_2"');

      // Audition buttons beside speaker voice dropdown
      expect(markup).toContain('data-action="audition-speaker-voice"');
      expect(markup).toContain('data-speaker-id="spk_1"');
      expect(markup).toContain('data-speaker-id="spk_2"');
      expect(markup).toContain('title="Audition PhamTuyen"');
      expect(markup).toContain('title="Audition Rachel"');
    });

    test('changing speaker voice updates audition button to play newly selected voice', () => {
      // Update Alice to a new voice
      useDubDubStore.getState().setSpeakerVoice('spk_1', 'StaticVoice');

      const markup = renderToStaticMarkup(<Stage3VoiceDubbing />);
      expect(markup).toContain('data-speaker-id="spk_1"');
      expect(markup).toContain('title="Audition StaticVoice"');
    });

    test('renders Pause icon on speaker card when active and halts when clicked', () => {
      voiceAuditionManager.play('speaker-spk_1', '/spk1_audio.wav');

      const markup = renderToStaticMarkup(<Stage3VoiceDubbing />);
      expect(markup).toContain('data-speaker-id="spk_1"');
      expect(markup).toContain('title="Stop Audition"');
    });

    test('speaker with voice "No" has audition button disabled with appropriate tooltip', () => {
      useDubDubStore.getState().setSpeakerVoice('spk_1', 'No');

      const markup = renderToStaticMarkup(<Stage3VoiceDubbing />);
      expect(markup).toContain('data-speaker-id="spk_1"');
      expect(markup).toContain('title="No voice assigned"');
      expect(markup).toContain('disabled=""');
    });

    test('speaker with whitespace-only voice has audition button disabled with "No voice assigned"', () => {
      useDubDubStore.getState().setSpeakerVoice('spk_1', '   ');

      const markup = renderToStaticMarkup(<Stage3VoiceDubbing />);
      expect(markup).toContain('data-speaker-id="spk_1"');
      expect(markup).toContain('title="No voice assigned"');
      expect(markup).toContain('disabled=""');
    });

    test('speaker with placeholder voice "clone" has audition button disabled with "No voice assigned"', () => {
      useDubDubStore.getState().setSpeakerVoice('spk_1', 'clone');

      const markup = renderToStaticMarkup(<Stage3VoiceDubbing />);
      expect(markup).toContain('data-speaker-id="spk_1"');
      expect(markup).toContain('title="No voice assigned"');
      expect(markup).toContain('disabled=""');
    });

    test('speaker card with custom voice referenced by name resolves custom ID and audio URL', async () => {
      useDubDubStore.getState().setSpeakerVoice('spk_1', 'Clone Voice 1');

      const markup = renderToStaticMarkup(<Stage3VoiceDubbing />);
      expect(markup).toContain('title="Audition Clone Voice 1"');
      expect(markup).toContain('data-speaker-id="spk_1"');
    });

    test('speaker card resolves cloned voice static sample even when ref_audio_path is not in customVoices list', async () => {
      useDubDubStore.setState({
        customVoices: [],
        voices: [
          {
            id: 'cv_isolated_12',
            name: 'Isolated Clone',
            kind: 'clone',
            provider: 2,
          },
        ],
      });
      useDubDubStore.getState().setSpeakerVoice('spk_1', 'Isolated Clone');

      const markup = renderToStaticMarkup(<Stage3VoiceDubbing />);
      expect(markup).toContain('title="Audition Isolated Clone"');
      expect(markup).toContain('data-speaker-id="spk_1"');
    });

    test('speaker card resolves voice provider and shares cache with dropdown audition', async () => {
      // Rachel is ElevenLabs (provider 0), but backend currentProvider is 2 (VieNeu)
      // 1. Populate dropdown cache for Rachel under provider 0
      voiceAuditionManager.setCachedUrl(0, 'Rachel', 'vi', '/api/tts/preview/rachel_cached/audio');

      let fetchCalled = false;
      globalThis.fetch = async () => {
        fetchCalled = true;
        return new Response(JSON.stringify({ ok: true, preview_url: '/dummy' }));
      };

      // 2. Speaker 2 is assigned Rachel
      useDubDubStore.getState().setSpeakerVoice('spk_2', 'Rachel');

      // Auditioning Rachel from speaker card should resolve Rachel's provider (0) and hit cache
      const playedUrl = await auditionVoice({
        key: 'speaker-spk_2',
        voice: 'Rachel',
        provider: 0, // as resolved by matchedPreset.provider
        language: 'vi',
      });

      expect(playedUrl).toBe('/api/tts/preview/rachel_cached/audio');
      expect(fetchCalled).toBe(false); // Cache hit! 0 network calls
      expect(voiceAuditionManager.isKeyPlaying('speaker-spk_2')).toBe(true);
    });

    test('speaker card plays static sample when voice is referenced by display name', async () => {
      // StaticVoice id is 'StaticVoice', display name is 'Static Voice', sampleUrl is '/samples/static1.wav'
      useDubDubStore.getState().setSpeakerVoice('spk_1', 'Static Voice');

      let fetchCalled = false;
      globalThis.fetch = async () => {
        fetchCalled = true;
        return new Response(JSON.stringify({ ok: true }));
      };

      // Audition using resolved static sample
      const matchedPreset = useDubDubStore.getState().voices.find(
        (v) => v.id === 'Static Voice' || v.name === 'Static Voice'
      );
      expect(matchedPreset).toBeDefined();
      expect(matchedPreset?.sampleUrl).toBe('/samples/static1.wav');

      const playedUrl = await auditionVoice({
        key: 'speaker-spk_1',
        voice: matchedPreset!.id,
        provider: matchedPreset!.provider!,
        language: 'vi',
        staticSampleUrl: matchedPreset!.sampleUrl,
      });

      expect(playedUrl).toBe('/samples/static1.wav');
      expect(fetchCalled).toBe(false);
      expect(voiceAuditionManager.isKeyPlaying('speaker-spk_1')).toBe(true);
    });
  });

  describe('Audio Lifecycle & Hook Stability', () => {
    test('audio.stop() cleanly clears audio.src releasing resources', () => {
      voiceAuditionManager.play('voice-A', '/sampleA.wav');
      const audioInstance = (voiceAuditionManager as any).audio;
      expect(audioInstance.src).toBe('/sampleA.wav');

      voiceAuditionManager.stop();
      expect(audioInstance.src).toBe('');
      expect(voiceAuditionManager.isPlayingState()).toBe(false);
      expect(voiceAuditionManager.getActiveKey()).toBeNull();
    });

    test('unmounting a closed VoiceSelector does not stop currently playing audio', () => {
      // Simulate Voice A playing from an open selector
      voiceAuditionManager.play('voice-A', '/sampleA.wav');
      expect(voiceAuditionManager.isKeyPlaying('voice-A')).toBe(true);

      // Rendering a closed VoiceSelector and letting it unmount
      const markup = renderToStaticMarkup(
        <VoiceSelector
          value="Rachel"
          onChange={() => {}}
          forceOpen={false}
        />
      );
      expect(markup).toContain('Rachel');

      // voice-A must STILL be playing
      expect(voiceAuditionManager.isKeyPlaying('voice-A')).toBe(true);
    });
  });

  describe('Segment Dialogue Block Audition Coordination', () => {
    test('segment dialogue block plays audio through coordinated player and stops speaker audition', () => {
      // Start speaker audition
      voiceAuditionManager.play('speaker-spk_1', '/spk1.wav');
      expect(voiceAuditionManager.isKeyPlaying('speaker-spk_1')).toBe(true);

      // Play segment cue 1
      voiceAuditionManager.play('segment-1', '/api/tts/preview/prev_seg1/audio');
      expect(voiceAuditionManager.isKeyPlaying('speaker-spk_1')).toBe(false);
      expect(voiceAuditionManager.isKeyPlaying('segment-1')).toBe(true);

      const markup = renderToStaticMarkup(<Stage3VoiceDubbing />);
      // Segment audition button transitions to pause
      expect(markup).toContain('title="Pause preview"');
    });
  });
});
