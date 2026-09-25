import { beforeEach, describe, expect, test } from 'bun:test';
import { renderToStaticMarkup } from 'react-dom/server';

import { Stage1Prepare } from '../src/screens/Stage1Prepare';
import { Stage2ReviewTranscript } from '../src/screens/Stage2ReviewTranscript';
import { Stage3VoiceDubbing } from '../src/screens/Stage3VoiceDubbing';
import { Stage4EditVideo } from '../src/screens/Stage4EditVideo';
import { useDubDubStore } from '../src/store';
import { buildPrepareJobRequest } from '../src/store/jobSlice';
import { buildTranslationRequest } from '../src/store/transcriptSlice';
import { VideoPlayer } from '../src/components/VideoPlayer';

const segment = {
  id: 1,
  startSec: 0,
  endSec: 2,
  startTime: '00:00.000',
  endTime: '00:02.000',
  sourceText: 'Hello world',
  targetText: 'Xin chao',
  speakerId: 'speaker-1',
};

beforeEach(() => {
  useDubDubStore.setState({
    activeProjectId: null,
    segments: [segment],
    voices: [{ id: 'voice-a', name: 'Voice A' }],
    speakerVoiceMap: {},
    segmentVoiceOverrides: {},
  });
});

describe('React four-stage workflow', () => {
  test.each([
    [Stage1Prepare, 'ASR Engine'],
    [Stage2ReviewTranscript, 'Batch Translate'],
    [Stage3VoiceDubbing, 'Multi-Speaker Voice Matrix'],
    [Stage4EditVideo, 'TIMELINE'],
  ])('renders %p behavior surface', (Screen, marker) => {
    expect(renderToStaticMarkup(<Screen />)).toContain(marker);
  });

  test('builds the Stage 1 ASR request from current selections', () => {
    const state = useDubDubStore.getState();
    useDubDubStore.setState({
      activeProjectId: 'project-1',
      backend: { ...state.backend, mediaId: 'media-1', config: { ...state.backend.config, recognType: 2 } },
      project: { ...state.project, verified: true },
      languages: {
        source: { code: 'en', name: 'English', flag: '', autoDetected: false },
        target: { code: 'vi', name: 'Vietnamese' },
        timingMode: 'voice',
      },
      engines: { speakerDiarization: true, speakerCount: 2, removeNoise: true, ocrSlideEngine: false },
    });

    expect(buildPrepareJobRequest(useDubDubStore.getState())).toMatchObject({
      mediaId: 'media-1',
      projectId: 'project-1',
      jobType: 'asr',
      options: {
        recognType: 2,
        sourceLanguage: 'en',
        targetLanguage: 'vi',
        timingMode: 'voice',
        removeNoise: true,
        speakerDiarization: true,
        speakerCount: 2,
      },
    });
  });

  test('Stage 1 renders Deepgram Parameters button and preserves custom deepgramOptions', () => {
    const store = useDubDubStore.getState();
    store.updateAsrProvider(1, 'nova-3'); // Deepgram
    store.updateDeepgramOptions({
      utt_split: 0.8,
      diarize_model: 'latest',
      extra: 'keywords=AI,DubDub&numerals=true',
    });

    const html = renderToStaticMarkup(<Stage1Prepare />);
    expect(html).toContain('data-testid="deepgram-options-btn"');
    expect(html).toContain('Deepgram Parameters');
    expect(html).toContain('utt_split=0.8s');

    const jobReq = buildPrepareJobRequest(useDubDubStore.getState());
    expect(jobReq.options.deepgramOptions).toMatchObject({
      utt_split: 0.8,
      diarize_model: 'latest',
      extra: 'keywords=AI,DubDub&numerals=true',
    });
  });

  test('builds the Stage 2 translation request with the selected method', () => {
    const state = useDubDubStore.getState();
    useDubDubStore.setState({
      activeProjectId: 'project-1',
      backend: { ...state.backend, config: { ...state.backend.config, translateType: 5, translationMode: 'srt' } },
      languages: {
        source: { code: 'en', name: 'English', flag: '', autoDetected: false },
        target: { code: 'vi', name: 'Vietnamese' },
        timingMode: 'voice',
      },
    });

    expect(buildTranslationRequest(useDubDubStore.getState())).toEqual({
      segments: [segment],
      sourceLanguage: 'en',
      targetLanguage: 'vi',
      translateType: 5,
      translationMode: 'srt',
    });
  });

  test('Stage 2 renders LLM Translation option, translation method, and video subtitle toggle', () => {
    const html = renderToStaticMarkup(<Stage2ReviewTranscript />);
    expect(html).toContain('LLM Translation:');
    expect(html).toContain('data-testid="translation-provider-select"');
    expect(html).toContain('data-testid="translation-method-select"');
    expect(html).toContain('data-testid="toggle-subtitles-btn"');
    expect(html).toContain('CC ON');
    expect(html).toContain('Batch Translate');
  });

  test('updating translation provider and method updates state and translation request', () => {
    const store = useDubDubStore.getState();
    store.updateTranslationProvider(2); // Gemini
    store.updateTranslationMode('text'); // Batch Text

    const updated = useDubDubStore.getState();
    expect(updated.backend.config.translateType).toBe(2);
    expect(updated.backend.config.translationMode).toBe('text');

    const req = buildTranslationRequest(updated);
    expect(req.translateType).toBe(2);
    expect(req.translationMode).toBe('text');
  });

  test('VideoPlayer subtitle overlay can be removed/hidden with initialSubtitlesVisible=false', () => {
    const withSubs = renderToStaticMarkup(
      <Stage2ReviewTranscript />
    );
    expect(withSubs).toContain('data-canvas-subtitle="true"');

    // Render Stage 2 when subtitles are toggled/hidden on the video
    const state = useDubDubStore.getState();
    useDubDubStore.setState({
      ...state,
      segments: [{ ...segment, targetText: 'Custom Translated Text' }],
    });

    const withoutSubs = renderToStaticMarkup(
      <VideoPlayer title="Test Player" subtitleVariant="dual" initialSubtitlesVisible={false} />
    );
    expect(withoutSubs).not.toContain('data-canvas-subtitle="true"');
    expect(withoutSubs).toContain('CC OFF');
  });

  test('keeps Stage 3 speaker defaults and per-segment overrides independent', () => {
    const store = useDubDubStore.getState();
    store.setSpeakerVoice('speaker-1', 'voice-a');
    store.setSegmentVoiceOverride(1, 'voice-b');
    expect(useDubDubStore.getState().getResolvedVoiceForSegment(segment)).toBe('voice-b');

    useDubDubStore.getState().clearSegmentVoiceOverride(1);
    expect(useDubDubStore.getState().getResolvedVoiceForSegment(segment)).toBe('voice-a');
  });

  test('clamps Stage 4 mix controls and restores muted values', () => {
    useDubDubStore.getState().setAudioMix('original', 175);
    expect(useDubDubStore.getState().editVideo.audioMix.original).toBe(150);
    useDubDubStore.getState().toggleAudioMute('original');
    expect(useDubDubStore.getState().editVideo.audioMix.original).toBe(0);
    useDubDubStore.getState().toggleAudioMute('original');
    expect(useDubDubStore.getState().editVideo.audioMix.original).toBe(150);
  });

  test('Stage 2 renders transcript segmentation options and allows choosing between Utterances and Paragraphs', () => {
    const store = useDubDubStore.getState();
    const utteranceSegments = [
      {
        id: 1,
        speaker: 'Speaker 1',
        speakerId: 'spk_1',
        speakerName: 'Speaker 1',
        speakerLabel: 'Speaker 1',
        speakerColor: 'amber',
        speakerCode: 'S1',
        startTime: '00:00:01,000',
        endTime: '00:00:03,500',
        startSec: 1.0,
        endSec: 3.5,
        text: 'Utterance 1',
        sourceText: 'Utterance 1',
        targetText: '',
        cps: 12.0,
        cpsStatus: 'Optimal' as const,
      },
      {
        id: 2,
        speaker: 'Speaker 2',
        speakerId: 'spk_2',
        speakerName: 'Speaker 2',
        speakerLabel: 'Speaker 2',
        speakerColor: 'secondary',
        speakerCode: 'S2',
        startTime: '00:00:03,800',
        endTime: '00:00:06,000',
        startSec: 3.8,
        endSec: 6.0,
        text: 'Utterance 2',
        sourceText: 'Utterance 2',
        targetText: '',
        cps: 11.5,
        cpsStatus: 'Optimal' as const,
      },
    ];

    const paragraphSegments = [
      {
        id: 1,
        speaker: 'Speaker 1',
        speakerId: 'spk_1',
        speakerName: 'Speaker 1',
        speakerLabel: 'Speaker 1',
        speakerColor: 'amber',
        speakerCode: 'S1',
        startTime: '00:00:01,000',
        endTime: '00:00:06,000',
        startSec: 1.0,
        endSec: 6.0,
        text: 'Utterance 1 Utterance 2',
        sourceText: 'Utterance 1 Utterance 2',
        targetText: '',
        cps: 11.8,
        cpsStatus: 'Optimal' as const,
      },
    ];

    store.setTranscriptOptions({
      utterances: utteranceSegments,
      paragraphs: paragraphSegments,
    });

    const html = renderToStaticMarkup(<Stage2ReviewTranscript />);
    expect(html).toContain('data-testid="select-utterances-btn"');
    expect(html).toContain('data-testid="select-paragraphs-btn"');
    expect(html).toContain('data-testid="segmentation-modal"');
    expect(html).toContain('Utterances (2)');
    expect(html).toContain('Paragraphs (1)');
    expect(html).toContain('Paragraphs (paragraph.transcript)');

    // Switch to paragraphs
    useDubDubStore.getState().selectSegmentationOption('paragraphs');
    expect(useDubDubStore.getState().selectedSegmentOption).toBe('paragraphs');
    expect(useDubDubStore.getState().segments).toHaveLength(1);
    expect(useDubDubStore.getState().segments[0].text).toBe('Utterance 1 Utterance 2');

    // Switch back to utterances
    useDubDubStore.getState().selectSegmentationOption('utterances');
    expect(useDubDubStore.getState().selectedSegmentOption).toBe('utterances');
    expect(useDubDubStore.getState().segments).toHaveLength(2);
  });

  test('selectProject restores currentStep, maxUnlockedStep, and segments from ASR stage', async () => {
    const savedProject = {
      id: 'proj-asr-123',
      name: 'Sample ASR Video',
      stage: 2,
      status: 'completed' as const,
      media_id: 'media-123',
      state: {
        currentStep: 2,
        segments: [
          {
            id: 1,
            startSec: 0,
            endSec: 3,
            startTime: '00:00:00,000',
            endTime: '00:00:03,000',
            sourceText: 'Restored ASR segment',
            targetText: '',
          },
        ],
        transcriptOptions: {
          utterances: [{ id: 1, sourceText: 'Restored ASR segment', startTime: '00:00:00,000', endTime: '00:00:03,000' }],
          paragraphs: [{ id: 1, sourceText: 'Restored ASR segment', startTime: '00:00:00,000', endTime: '00:00:03,000' }],
        },
      },
    };

    const originalFetch = globalThis.fetch;
    globalThis.fetch = (async (url: string | URL | Request) => {
      const urlStr = String(url);
      if (urlStr.includes('/api/projects/proj-asr-123')) {
        return new Response(JSON.stringify(savedProject), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } });
    }) as any;

    try {
      // Start in step 1 with empty segments
      useDubDubStore.setState({
        currentStep: 1,
        activeProjectId: null,
        segments: [],
      });

      await useDubDubStore.getState().selectProject('proj-asr-123');

      const state = useDubDubStore.getState();
      expect(state.activeProjectId).toBe('proj-asr-123');
      expect(state.currentStep).toBe(2);
      expect(state.maxUnlockedStep).toBeGreaterThanOrEqual(2);
      expect(state.segments).toHaveLength(1);
      expect(state.segments[0].sourceText).toBe('Restored ASR segment');
      expect(state.transcriptOptions?.utterances).toHaveLength(1);
      expect(state.project.previewUrl).toBe('/api/media/media-123/file');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('startPrepareJob ensures activeProjectId exists, submits job, and advances to step 2', async () => {
    const originalFetch = globalThis.fetch;
    let createdProjectId = '';
    let submittedBody: any = null;

    globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
      const urlStr = String(url);
      if (urlStr.endsWith('/api/projects') && init?.method === 'POST') {
        const body = JSON.parse(init.body as string);
        createdProjectId = 'new-project-999';
        return new Response(JSON.stringify({ id: createdProjectId, name: body.name, stage: 1 }), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (urlStr.includes('/api/jobs') && init?.method === 'POST') {
        submittedBody = JSON.parse(init.body as string);
        return new Response(
          JSON.stringify({
            id: 'job-asr-999',
            status: 'succeeded',
            segments: [
              {
                id: 1,
                startSec: 0,
                endSec: 2,
                startTime: '00:00:00,000',
                endTime: '00:00:02,000',
                sourceText: 'Finished ASR speech',
                targetText: '',
              },
            ],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      }
      return new Response(JSON.stringify({ projects: [] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }) as any;

    try {
      useDubDubStore.setState({
        activeProjectId: null,
        currentStep: 1,
        segments: [],
        backend: {
          ...useDubDubStore.getState().backend,
          mediaId: 'media-test-1',
          config: {
            ...useDubDubStore.getState().backend.config,
            recognType: 1,
          },
        },
        project: {
          ...useDubDubStore.getState().project,
          filename: 'test-dub.mp4',
          verified: true,
        },
      });

      await useDubDubStore.getState().startPrepareJob();

      const state = useDubDubStore.getState();
      expect(state.activeProjectId).toBe('new-project-999');
      expect(submittedBody?.projectId).toBe('new-project-999');
      expect(state.currentStep).toBe(2);
      expect(state.maxUnlockedStep).toBeGreaterThanOrEqual(2);
      expect(state.segments).toHaveLength(1);
      expect(state.segments[0].sourceText).toBe('Finished ASR speech');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});
