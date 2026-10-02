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
import { WorkflowStepper } from '../src/components/WorkflowStepper';
import { ErrorBoundary } from '../src/components/ErrorBoundary';
import { StatusFooter } from '../src/components/StatusFooter';
import { ProjectDrawer } from '../src/components/ProjectDrawer';

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
    backend: {
      ready: true,
      error: null,
      mediaId: null,
      status: 'idle',
      message: '',
      options: {
        languages: [
          { code: 'zh-cn', name: 'Simplified Chinese' },
          { code: 'vi', name: 'Vietnamese' },
          { code: 'en', name: 'English' },
          { code: 'ja', name: 'Japanese' },
        ],
        asrProviders: [],
        translationProviders: [],
        translationModes: [],
        voices: [],
      },
      config: {
        recognType: 1,
        translateType: 0,
        translationMode: 'srt',
        ttsType: 2,
        modelName: 'nova-3',
        voiceRole: '',
        useCuda: false,
      },
    },
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
      engines: { speakerDiarization: true, speakerCount: 2, ocrSlideEngine: false },
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
        speakerDiarization: true,
        speakerCount: 2,
      },
    });
    expect(buildPrepareJobRequest(useDubDubStore.getState()).options).not.toHaveProperty('removeNoise');
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

  test('Reset is available on all four stages and Stage 1 explains its options without Denoise', () => {
    const html = renderToStaticMarkup(<Stage1Prepare />);
    expect(html).not.toContain('Denoise Background Audio');
    for (const explanation of [
      'Language spoken in the source media',
      'Language for translated subtitles',
      'Choose whether speech, video speed',
      'Speech recognition service',
      'Recognition model used',
      'Adjust Deepgram transcription',
      'Format recognized dates',
      'Add punctuation',
      'Identify who is speaking',
      'supported NVIDIA GPU',
    ]) expect(html).toContain(explanation);
    for (const step of [1, 2, 3, 4]) {
      useDubDubStore.setState({ currentStep: step, activeProjectId: 'project-1' });
      expect(renderToStaticMarkup(<StatusFooter />)).toContain(`data-testid="reset-stage-${step}-btn"`);
    }
  });

  test('reset waits for pending autosave, then reloads cleared project state', async () => {
    const originalFetch = globalThis.fetch;
    const calls: string[] = [];
    let finishSave!: () => void;
    const saveGate = new Promise<void>((resolve) => { finishSave = resolve; });
    const project = {
      id: 'reset-project', name: 'Reset project', media_id: 'media-1', stage: 1,
      state: {
        currentStep: 1, forceAsr: true, segments: [],
        backend: { mediaId: 'media-1', config: { recognType: 1, modelName: 'nova-3' } },
        project: { verified: true, filename: 'source.mp4' },
      },
    };
    globalThis.fetch = (async (url: string, init?: RequestInit) => {
      if (init?.method === 'PUT') {
        calls.push('save');
        await saveGate;
      } else if (url.includes('/stages/1/reset')) {
        calls.push('reset');
      }
      const body = url === '/api/projects' ? { projects: [project] } : project;
      return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }) as any;

    try {
      useDubDubStore.setState({ activeProjectId: 'reset-project', segments: [segment], forceAsr: false });
      useDubDubStore.getState().triggerAutosave();
      const reset = useDubDubStore.getState().resetStage(1);
      await new Promise((resolve) => setTimeout(resolve, 0));
      expect(calls).not.toContain('reset');
      finishSave();
      await reset;
      expect(calls).toEqual(['save', 'reset']);
      expect(useDubDubStore.getState().segments).toEqual([]);
      expect(useDubDubStore.getState().forceAsr).toBe(true);
      expect(useDubDubStore.getState().backend.mediaId).toBe('media-1');
    } finally {
      finishSave();
      globalThis.fetch = originalFetch;
    }
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

  test('VideoPlayer renders subtitles with blurred outline, white text, and black outline', () => {
    useDubDubStore.setState({
      segments: [{ ...segment, startSec: 0, endSec: 5, targetText: 'Subtitles Blurred Outline Test' }],
      playback: { ...useDubDubStore.getState().playback, currentTime: 1.0 },
    });

    // 1. Dual mode (Stage 2 & 3)
    const dualHtml = renderToStaticMarkup(
      <VideoPlayer title="Dual Player" subtitleVariant="dual" initialSubtitlesVisible={true} />
    );
    expect(dualHtml).toContain('data-canvas-subtitle="true"');
    expect(dualHtml).toContain('Subtitles Blurred Outline Test');
    // White text
    expect(dualHtml).toContain('color:#FFFFFF');
    // Black outline around text
    expect(dualHtml).toContain('-webkit-text-stroke:1.5px #000000');
    // Blurred outline around them
    expect(dualHtml).toContain('rgba(0,0,0,0.95)');
    expect(dualHtml).toContain('drop-shadow');

    // 2. CapCut mode (Stage 4)
    const capcutHtml = renderToStaticMarkup(
      <VideoPlayer title="CapCut Player" subtitleVariant="capcut" initialSubtitlesVisible={true} />
    );
    expect(capcutHtml).toContain('data-canvas-subtitle="true"');
    expect(capcutHtml).toContain('-webkit-text-stroke:2px #000000');
    expect(capcutHtml).toContain('drop-shadow');
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

  test('createNewProject and selectProject on empty project resets media state and renders upload button without F5', async () => {
    const originalFetch = globalThis.fetch;
    const emptyNewProject = {
      id: 'proj-new-001',
      name: 'Brand New Blank Project',
      stage: 1,
      status: 'pending' as const,
      media_id: null,
      state: null,
    };

    globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
      const urlStr = String(url);
      if (urlStr.endsWith('/api/projects') && init?.method === 'POST') {
        return new Response(JSON.stringify(emptyNewProject), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (urlStr.includes('/api/projects/proj-new-001')) {
        return new Response(JSON.stringify(emptyNewProject), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response(JSON.stringify({ projects: [emptyNewProject] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }) as any;

    try {
      // Suppose user previously had an active project with a video loaded
      useDubDubStore.setState({
        activeProjectId: 'proj-old',
        currentStep: 2,
        backend: {
          ...useDubDubStore.getState().backend,
          mediaId: 'media-old-999',
        },
        project: {
          ...useDubDubStore.getState().project,
          filename: 'old-video.mp4',
          previewUrl: '/api/media/media-old-999/file',
          verified: true,
        },
      });

      // User creates and activates new project
      const newId = await useDubDubStore.getState().createNewProject('Brand New Blank Project');
      expect(newId).toBe('proj-new-001');

      const state = useDubDubStore.getState();
      expect(state.activeProjectId).toBe('proj-new-001');
      expect(state.currentStep).toBe(1);
      expect(state.backend.mediaId).toBeNull();
      expect(state.project.previewUrl).toBeUndefined();
      expect(state.project.verified).toBe(false);

      // Render Stage 1: upload button/dropzone must be present, video preview must NOT be present
      const html = renderToStaticMarkup(<Stage1Prepare />);
      expect(html).toContain('Select Media File');
      expect(html).toContain('Drop video here, or click to browse');
      expect(html).not.toContain('data-source-preview="true"');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('reopening an old project restores video preview URL, cleanses legacy blob URLs, and renders player', async () => {
    const originalFetch = globalThis.fetch;
    let savedPutBody: any = null;

    globalThis.fetch = ((url: string, init?: RequestInit) => {
      if (url.includes('/api/projects/proj-saved-456') && init?.method === 'PUT') {
        savedPutBody = JSON.parse(init.body as string);
        return new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('/api/projects/proj-saved-456')) {
        return new Response(
          JSON.stringify({
            project: {
              id: 'proj-saved-456',
              name: 'Interview Video Project',
              media_id: 'media-777',
              stage: 1,
              state: {
                currentStep: 1,
                project: {
                  filename: 'interview_clip.mp4',
                  // Legacy dead blob URL saved by old version
                  previewUrl: 'blob:http://localhost:5173/revoked-blob-uuid',
                  verified: true,
                },
              },
            },
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }) as any;

    try {
      // Reopen the saved project
      await useDubDubStore.getState().selectProject('proj-saved-456');

      const state = useDubDubStore.getState();
      expect(state.activeProjectId).toBe('proj-saved-456');
      expect(state.backend.mediaId).toBe('media-777');
      expect(state.project.verified).toBe(true);
      // Must be cleansed from dead blob URL to persistent backend endpoint
      expect(state.project.previewUrl).toBe('/api/media/media-777/file');

      // Video player in Stage 1 must be rendered with source pointing to media file
      const html = renderToStaticMarkup(<Stage1Prepare />);
      expect(html).toContain('data-source-preview="true"');
      expect(html).toContain('src="/api/media/media-777/file"');
      expect(html).toContain('Stream Verified');

      // Trigger autosave and verify payload has clean mediaId and previewUrl
      useDubDubStore.getState().triggerAutosave();
      await new Promise((r) => setTimeout(r, 10));

      expect(savedPutBody).toBeTruthy();
      expect(savedPutBody.media_id).toBe('media-777');
      expect(savedPutBody.state.backend.mediaId).toBe('media-777');
      expect(savedPutBody.state.project.previewUrl).toBe('/api/media/media-777/file');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('Stage 2 renders language selection options, allows changing source and target, and applies them to batch translation', async () => {
    const originalFetch = globalThis.fetch;
    let translatePayload: any = null;

    globalThis.fetch = ((url: string, init?: RequestInit) => {
      if (url.includes('/api/translate') && init?.method === 'POST') {
        translatePayload = JSON.parse(init.body as string);
        return new Response(
          JSON.stringify({
            ok: true,
            segments: [
              {
                id: 1,
                line: 1,
                targetText: 'Hello world translated to English',
              },
            ],
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }) as any;

    try {
      useDubDubStore.setState({
        segments: [segment],
        languages: {
          source: { code: 'zh-cn', name: 'Simplified Chinese', flag: '', autoDetected: false },
          target: { code: 'vi', name: 'Vietnamese' },
          timingMode: 'voice',
        },
      });

      // 1. Verify Stage 2 markup renders language selector dropdowns
      const html = renderToStaticMarkup(<Stage2ReviewTranscript />);
      expect(html).toContain('data-testid="translation-source-lang-select"');
      expect(html).toContain('data-testid="translation-target-lang-select"');
      expect(html).toContain('Language Route:');
      expect(html).toContain('Simplified Chinese');
      expect(html).toContain('Vietnamese');

      // 2. Change source to Japanese and target to English in Stage 2
      useDubDubStore.getState().updateSourceLanguage('ja', 'Japanese');
      useDubDubStore.getState().updateTargetLanguage('en', 'English');

      const stateAfterUpdate = useDubDubStore.getState();
      expect(stateAfterUpdate.languages.source.code).toBe('ja');
      expect(stateAfterUpdate.languages.target.code).toBe('en');

      // 3. Trigger batch translation and verify payload
      await useDubDubStore.getState().runBatchTranslation();

      expect(translatePayload).toBeTruthy();
      expect(translatePayload.sourceLanguage).toBe('ja');
      expect(translatePayload.targetLanguage).toBe('en');

      // 4. Verify segment target text was updated from translation response
      const updatedSegments = useDubDubStore.getState().segments;
      expect(updatedSegments[0].targetText).toBe('Hello world translated to English');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('runBatchTranslation correctly applies targetText when response has original source in text property', async () => {
    const originalFetch = globalThis.fetch;

    globalThis.fetch = ((url: string, init?: RequestInit) => {
      if (url.includes('/api/translate') && init?.method === 'POST') {
        return new Response(
          JSON.stringify({
            ok: true,
            segments: [
              {
                id: 1,
                text: 'Xin chào mọi người',
                sourceText: 'Hello world',
                targetText: 'Xin chào mọi người',
              },
            ],
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }) as any;

    try {
      useDubDubStore.setState({
        segments: [{
          id: 1,
          startTime: '00:00.000',
          endTime: '00:02.000',
          startSec: 0,
          endSec: 2,
          text: 'Hello world',
          sourceText: 'Hello world',
          targetText: '',
          speakerId: 'spk-1',
        }],
      });

      await useDubDubStore.getState().runBatchTranslation();

      const segs = useDubDubStore.getState().segments;
      expect(segs[0].targetText).toBe('Xin chào mọi người');
      expect(segs[0].sourceText).toBe('Hello world');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('translateSingleSegment translates individual segment and applies targetText to transcript', async () => {
    const originalFetch = globalThis.fetch;

    globalThis.fetch = ((url: string, init?: RequestInit) => {
      if (url.includes('/api/translate') && init?.method === 'POST') {
        return new Response(
          JSON.stringify({
            ok: true,
            segments: [
              {
                id: 1,
                targetText: 'Đoạn văn được dịch riêng lẻ',
                text: 'Đoạn văn được dịch riêng lẻ',
                sourceText: 'Single translated paragraph',
              },
            ],
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }) as any;

    try {
      useDubDubStore.setState({
        segments: [{
          id: 1,
          startTime: '00:00.000',
          endTime: '00:02.000',
          startSec: 0,
          endSec: 2,
          text: 'Single translated paragraph',
          sourceText: 'Single translated paragraph',
          targetText: '',
          speakerId: 'spk-1',
        }],
      });

      await useDubDubStore.getState().translateSingleSegment(1);

      const segs = useDubDubStore.getState().segments;
      expect(segs[0].targetText).toBe('Đoạn văn được dịch riêng lẻ');
      expect(segs[0].sourceText).toBe('Single translated paragraph');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('ErrorBoundary renders fallback error UI when state hasError is true', () => {
    const error = new Error('Test explosion');
    const derived = ErrorBoundary.getDerivedStateFromError(error);
    expect(derived.hasError).toBe(true);
    expect(derived.error).toBe(error);

    const boundary = new ErrorBoundary({ fallbackTitle: 'Critical Render Issue', children: null });
    boundary.state = { hasError: true, error, errorInfo: null };
    const html = renderToStaticMarkup(boundary.render() as any);
    expect(html).toContain('Critical Render Issue');
    expect(html).toContain('Test explosion');
    expect(html).toContain('Return to Stage 1');
  });

  test('selectProject normalizes malformed project state and prevents render crashes', async () => {
    const originalFetch = globalThis.fetch;
    const malformedProject = {
      id: 'proj-malformed-001',
      name: 'Malformed State Project',
      stage: 2,
      status: 'completed' as const,
      media_id: 'med-001',
      state: {
        currentStep: 2,
        languages: {
          source: 'zh-cn',
          target: 'vi',
        },
        speakers: [
          { id: 101, name: 'Numeric Speaker' },
        ],
        segments: [
          { id: 1, text: 'Raw text only' },
        ],
      },
    };

    globalThis.fetch = (async (url: string) => {
      if (String(url).includes('/api/projects/proj-malformed-001')) {
        return new Response(JSON.stringify(malformedProject), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    }) as any;

    try {
      await useDubDubStore.getState().selectProject('proj-malformed-001');

      const state = useDubDubStore.getState();
      expect(state.languages.source.code).toBe('zh-cn');
      expect(state.languages.target.code).toBe('vi');
      expect(state.speakers[0].code).toBe('10');
      expect(state.segments[0].sourceText).toBe('Raw text only');
      expect(state.segments[0].targetText).toBe('');

      const stepperHtml = renderToStaticMarkup(<WorkflowStepper />);
      expect(stepperHtml).toContain('ZH ➔ VI');
      expect(stepperHtml).toContain('Malformed State Project');

      const stage2Html = renderToStaticMarkup(<Stage2ReviewTranscript />);
      expect(stage2Html).toContain('Raw text only');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('selectProject on non-existent project (404) cleanses activeProjectId and avoids white screen', async () => {
    const originalFetch = globalThis.fetch;
    const originalLocalStorage = (globalThis as any).localStorage;
    const storeMap = new Map<string, string>();
    (globalThis as any).localStorage = {
      getItem: (k: string) => storeMap.get(k) ?? null,
      setItem: (k: string, v: string) => storeMap.set(k, v),
      removeItem: (k: string) => storeMap.delete(k),
      clear: () => storeMap.clear(),
    };

    globalThis.fetch = (async () => {
      return new Response('Not Found', { status: 404 });
    }) as any;

    try {
      (globalThis as any).localStorage.setItem('dubdub_active_project_id', 'proj-non-existent');
      await useDubDubStore.getState().selectProject('proj-non-existent');

      expect(useDubDubStore.getState().activeProjectId).toBeNull();
      expect((globalThis as any).localStorage.getItem('dubdub_active_project_id')).toBeNull();
    } finally {
      globalThis.fetch = originalFetch;
      (globalThis as any).localStorage = originalLocalStorage;
    }
  });

  test('Stage3VoiceDubbing renders multiple speakers and cue overrides cleanly without maximum update depth error', () => {
    useDubDubStore.setState({
      segments: [
        {
          id: 1,
          startSec: 0,
          endSec: 2,
          startTime: '00:00.000',
          endTime: '00:02.000',
          sourceText: 'Hello world',
          targetText: 'Xin chao',
          speakerId: 'spk_1',
          speakerName: 'Alice',
        },
        {
          id: 2,
          startSec: 2,
          endSec: 4,
          startTime: '00:02.000',
          endTime: '00:04.000',
          sourceText: 'Good morning',
          targetText: 'Chao buoi sang',
          speakerId: 'spk_2',
          speakerName: 'Bob',
        },
      ],
      speakers: [
        { id: 'spk_1', name: 'Alice', code: 'AL' },
        { id: 'spk_2', name: 'Bob', code: 'BO' },
      ],
      speakerVoiceMap: { spk_1: 'voice-a', spk_2: 'voice-b' },
      segmentVoiceOverrides: { 2: 'voice-c' },
      tuning: { pace: 1.1, timbreWarmth: 75, ducking: '85/15' },
    });

    const html = renderToStaticMarkup(<Stage3VoiceDubbing />);
    expect(html).toContain('Alice');
    expect(html).toContain('Bob');
    // Tuning sliders removed as requested
    expect(html).not.toContain('Voice Synthesis Tuning');
    // Speaker filter dropdown and pill buttons
    expect(html).toContain('data-testid="stage3-speaker-filter"');
    expect(html).toContain('All Speakers (2)');
    expect(html).toContain('data-testid="filter-pill-spk_1"');
    expect(html).toContain('data-testid="filter-pill-spk_2"');
    expect(html).toContain('Dialogue Cue Overrides');
  });

  test('Stage 3 renders speaker badge with name, code, color, both source and target text, and voice preview audition controls', () => {
    useDubDubStore.setState({
      segments: [
        {
          id: 1,
          startSec: 0,
          endSec: 3.5,
          startTime: '00:00.000',
          endTime: '00:03.500',
          sourceText: 'Welcome to Stage 3 AI dubbing.',
          targetText: 'Chao mung den voi Stage 3 long tieng AI.',
          speakerId: 'spk_1',
          speakerName: 'Alex Carter',
          speakerCode: 'AC',
          speakerColor: 'amber',
          previewAudioUrl: '/api/tts/preview/prev_sample123/audio',
        },
        {
          id: 2,
          startSec: 3.5,
          endSec: 7.0,
          startTime: '00:03.500',
          endTime: '00:07.000',
          sourceText: 'Let us test voice preview and speaker cast.',
          targetText: 'Hay cung thu tinh nang nghe thu giong.',
          speakerId: 'spk_2',
          speakerName: 'Elena Rostova',
          speakerCode: 'ER',
          speakerColor: 'secondary',
        },
      ],
      speakers: [
        { id: 'spk_1', name: 'Alex Carter', code: 'AC', color: 'amber' },
        { id: 'spk_2', name: 'Elena Rostova', code: 'ER', color: 'secondary' },
      ],
      speakerVoiceMap: { spk_1: 'Rachel', spk_2: 'Phạm Tuyên' },
      segmentVoiceOverrides: { 2: 'Custom: Voice1' },
      tuning: { pace: 1.0, timbreWarmth: 62, ducking: '85/15' },
    });

    const html = renderToStaticMarkup(<Stage3VoiceDubbing />);

    // Speaker badges in blocks
    expect(html).toContain('Alex Carter');
    expect(html).toContain('AC');
    expect(html).toContain('Elena Rostova');
    expect(html).toContain('ER');

    // Both source text and editable target text present
    expect(html).toContain('Welcome to Stage 3 AI dubbing.');
    expect(html).toContain('Chao mung den voi Stage 3 long tieng AI.');
    expect(html).toContain('stage3-1');
    expect(html).toContain('stage3-2');

    // Voice preview and audition buttons
    expect(html).toContain('data-action="generate-voice-preview"');
    expect(html).toContain('data-action="play-voice-preview"');

    // Seek buttons and dual-level selection buttons
    expect(html).toContain('data-action="seek-segment"');
    expect(html).toContain('data-action="reset-segment-voice"');
    expect(html).toContain('data-action="set-speaker-default"');
    expect(html).toContain('data-action="proceed-to-edit-video"');
  });

  test('Stage 3 renders Auto Speed Fit toggle and updates speed cap setting', () => {
    useDubDubStore.setState({
      autoFitVoiceSpeed: true,
      maxSpeedRate: 1.25,
      segments: [
        {
          id: 1,
          startSec: 0,
          endSec: 2,
          startTime: '00:00.000',
          endTime: '00:02.000',
          sourceText: 'Hello',
          targetText: 'Xin chao',
          speakerId: 'spk_1',
        },
      ],
      speakers: [{ id: 'spk_1', name: 'Alex', code: 'AL', color: 'amber' }],
    });

    const html = renderToStaticMarkup(<Stage3VoiceDubbing />);
    expect(html).toContain('data-testid="auto-speed-toggle"');
    expect(html).toContain('Auto Speed');
    expect(html).toContain('data-testid="max-speed-selector"');
    expect(html).toContain('Max 1.25');

    // Test store setters
    useDubDubStore.getState().setAutoFitVoiceSpeed(false);
    expect(useDubDubStore.getState().autoFitVoiceSpeed).toBe(false);

    useDubDubStore.getState().setMaxSpeedRate(1.35);
    expect(useDubDubStore.getState().maxSpeedRate).toBe(1.35);

    // Re-render with autoFitVoiceSpeed=false: selector is hidden
    const htmlDisabled = renderToStaticMarkup(<Stage3VoiceDubbing />);
    expect(htmlDisabled).toContain('data-testid="auto-speed-toggle"');
    expect(htmlDisabled).not.toContain('data-testid="max-speed-selector"');
  });

  test('Stage 3 footer primary button renders Generate Dubbing when pending and transitions to Proceed to Edit Video when completed', () => {
    useDubDubStore.setState({
      currentStep: 3,
      dubbingStatus: 'idle',
    });

    // Pending state -> Generate Dubbing
    let footerHtml = renderToStaticMarkup(<StatusFooter />);
    expect(footerHtml).toContain('Generate Dubbing');

    // Completed state -> Proceed to Edit Video
    useDubDubStore.setState({ dubbingStatus: 'completed' });
    footerHtml = renderToStaticMarkup(<StatusFooter />);
    expect(footerHtml).toContain('Proceed to Edit Video');
  });

  test('Stage 3 waits for stitched audio before opening Stage 4', async () => {
    const originalFetch = globalThis.fetch;
    let finishAssembly!: (response: Response) => void;
    const assembly = new Promise<Response>((resolve) => { finishAssembly = resolve; });
    const calls: string[] = [];
    try {
      globalThis.fetch = async (url: string | URL | Request) => {
        calls.push(String(url));
        if (String(url).endsWith('/dubbing/assemble')) return assembly;
        return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      };
      useDubDubStore.setState({ activeProjectId: 'stage3-project', currentStep: 3, segments: [{ ...segment, previewAudioId: 'prev_aaaaaaaaaaaa' }] });
      const pending = useDubDubStore.getState().enterStage4();
      expect(useDubDubStore.getState().currentStep).toBe(3);
      finishAssembly(new Response(JSON.stringify({ ok: true, audio_url: '/api/projects/stage3-project/dubbing/audio' }), {
        status: 200, headers: { 'Content-Type': 'application/json' },
      }));
      await pending;
      expect(useDubDubStore.getState().currentStep).toBe(4);
      expect(useDubDubStore.getState().assembledDubUrl).toContain('/api/projects/stage3-project/dubbing/audio');
      expect(calls[0]).toBe('/api/projects/stage3-project/dubbing/assemble');
      expect(renderToStaticMarkup(<Stage4EditVideo />)).toContain('Stitched Stage 3 voiceover loaded');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('Stage 3 stays open when voiceover assembly fails', async () => {
    const originalFetch = globalThis.fetch;
    try {
      globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Generate a voice preview for segment 1' }), {
        status: 400, headers: { 'Content-Type': 'application/json' },
      });
      useDubDubStore.setState({ activeProjectId: 'stage3-project', currentStep: 3 });
      await useDubDubStore.getState().enterStage4();
      expect(useDubDubStore.getState().currentStep).toBe(3);
      expect(useDubDubStore.getState().dubbingError).toContain('segment 1');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('Stage 3 synchronizes segmentVoiceOverrides and segment.voiceOverride, and resets dubbingStatus on edit', () => {
    useDubDubStore.setState({
      segments: [
        {
          id: 1,
          startSec: 0,
          endSec: 2,
          startTime: '00:00.000',
          endTime: '00:02.000',
          sourceText: 'Hello',
          targetText: 'Xin chao',
          speakerId: 'spk_1',
          speakerName: 'Speaker 1',
        },
        {
          id: 2,
          startSec: 2,
          endSec: 4,
          startTime: '00:02.000',
          endTime: '00:04.000',
          sourceText: 'World',
          targetText: 'The gioi',
          speakerId: 'spk_2',
          voiceOverride: 'Initial-Override',
        },
      ],
      speakerVoiceMap: { spk_1: 'Voice-Spk1', spk_2: 'Voice-Spk2' },
      segmentVoiceOverrides: {},
      dubbingStatus: 'completed',
    });

    const store = useDubDubStore.getState();

    // segment 2 has voiceOverride on segment itself
    expect(store.getResolvedVoiceForSegment(store.segments[1])).toBe('Initial-Override');

    // setSegmentVoiceOverride on segment 1
    store.setSegmentVoiceOverride(1, 'Overridden-Voice-1');
    const updatedState = useDubDubStore.getState();
    expect(updatedState.segmentVoiceOverrides[1]).toBe('Overridden-Voice-1');
    expect(updatedState.segments[0].voiceOverride).toBe('Overridden-Voice-1');
    // dubbingStatus should reset from completed to idle
    expect(updatedState.dubbingStatus).toBe('idle');

    // mark completed and then clear override
    useDubDubStore.setState({ dubbingStatus: 'completed' });
    useDubDubStore.getState().clearSegmentVoiceOverride(1);
    const clearedState = useDubDubStore.getState();
    expect(clearedState.segmentVoiceOverrides[1]).toBeUndefined();
    expect(clearedState.segments[0].voiceOverride).toBeUndefined();
    expect(clearedState.dubbingStatus).toBe('idle');
    expect(clearedState.getResolvedVoiceForSegment(clearedState.segments[0])).toBe('Voice-Spk1');

    // mark completed and test that modifying target text resets dubbingStatus to idle
    useDubDubStore.setState({ dubbingStatus: 'completed' });
    useDubDubStore.getState().updateSegmentText(1, 'Ban dich moi', true);
    expect(useDubDubStore.getState().dubbingStatus).toBe('idle');
  });

  test('Stage 3 handles diarization numeric speaker ID 0 without collapsing into spk_1', () => {
    useDubDubStore.setState({
      segments: [
        {
          id: 1,
          startSec: 0,
          endSec: 2,
          startTime: '00:00.000',
          endTime: '00:02.000',
          sourceText: 'Speaker zero text',
          targetText: 'Van ban nguoi noi 0',
          speakerId: '0',
        },
        {
          id: 2,
          startSec: 2,
          endSec: 4,
          startTime: '00:02.000',
          endTime: '00:04.000',
          sourceText: 'Speaker one text',
          targetText: 'Van ban nguoi noi 1',
          speakerId: '1',
        },
      ],
      speakers: [],
      speakerVoiceMap: { '0': 'Voice-Zero', '1': 'Voice-One' },
    });

    const store = useDubDubStore.getState();
    const distinct = store.getDistinctSpeakers();
    expect(distinct.length).toBe(2);
    expect(distinct.some((s) => s.id === '0')).toBe(true);
    expect(distinct.some((s) => s.id === '1')).toBe(true);

    // Resolved voice for speaker 0 must be Voice-Zero
    expect(store.getResolvedVoiceForSegment(store.segments[0])).toBe('Voice-Zero');
    expect(store.getResolvedVoiceForSegment(store.segments[1])).toBe('Voice-One');
  });

  test('Stage 3 renders Generate Voice Preview when segment voice differs from previewVoice', () => {
    useDubDubStore.setState({
      segments: [
        {
          id: 1,
          startSec: 0,
          endSec: 2,
          startTime: '00:00.000',
          endTime: '00:02.000',
          sourceText: 'Hello',
          targetText: 'Xin chao',
          speakerId: 'spk_1',
          previewAudioUrl: '/api/tts/preview/prev_old/audio',
          previewVoice: 'OldVoice',
          voiceOverride: 'NewVoice',
        },
      ],
      speakers: [{ id: 'spk_1', name: 'Alex', code: 'AL' }],
      speakerVoiceMap: { spk_1: 'OldVoice' },
      segmentVoiceOverrides: { 1: 'NewVoice' },
    });

    const html = renderToStaticMarkup(<Stage3VoiceDubbing />);
    // Since activeVoice is NewVoice and previewVoice is OldVoice, the button should offer Generate Voice Preview
    expect(html).toContain('Generate Voice Preview');
    expect(html).toContain('Audition (OldVoice)');
  });

  test('clicking a block plays video from that block start time until its end time', () => {
    useDubDubStore.setState({
      segments: [
        {
          id: 1,
          startSec: 2.5,
          endSec: 5.0,
          startTime: '00:02.500',
          endTime: '00:05.000',
          sourceText: 'Hello world',
          targetText: 'Xin chao the gioi',
          speakerId: 'spk_1',
        },
        {
          id: 2,
          startSec: 6.0,
          endSec: 9.5,
          startTime: '00:06.000',
          endTime: '00:09.500',
          sourceText: 'Second segment',
          targetText: 'Doan thu hai',
          speakerId: 'spk_2',
        },
      ],
      playback: {
        currentTime: 0,
        formattedTime: '00:00.000',
        duration: 20,
        isPlaying: false,
        playbackSpeed: 1.0,
        audioChannel: 'dub',
        stopAtTime: null,
        seekRequest: null,
      },
    });

    const store = useDubDubStore.getState();

    // Trigger seekAndPlay for block 1 (start 2.5 -> end 5.0)
    store.seekAndPlay(2.5, 5.0, 1);

    const afterSeek = useDubDubStore.getState();
    expect(afterSeek.playback.currentTime).toBe(2.5);
    expect(afterSeek.playback.isPlaying).toBe(true);
    expect(afterSeek.playback.stopAtTime).toBe(5.0);
    expect(afterSeek.activeSegmentId).toBe(1);
    expect(afterSeek.playback.seekRequest?.play).toBe(true);
    expect(afterSeek.playback.seekRequest?.time).toBe(2.5);
    expect(afterSeek.playback.seekRequest?.stopAt).toBe(5.0);

    // Progress time while playing inside segment duration
    store.updatePlaybackTime(3.8);
    const midPlayback = useDubDubStore.getState();
    expect(midPlayback.playback.currentTime).toBe(3.8);
    expect(midPlayback.playback.isPlaying).toBe(true);
    expect(midPlayback.playback.stopAtTime).toBe(5.0);

    // Reaching segment endSec must automatically pause video and clear stopAtTime
    store.updatePlaybackTime(5.0);
    const endPlayback = useDubDubStore.getState();
    expect(endPlayback.playback.currentTime).toBe(5.0);
    expect(endPlayback.playback.isPlaying).toBe(false);
    expect(endPlayback.playback.stopAtTime).toBe(null);

    // Now clicking block 2 (start 6.0 -> end 9.5)
    store.seekAndPlay(6.0, 9.5, 2);
    const seg2Play = useDubDubStore.getState();
    expect(seg2Play.playback.currentTime).toBe(6.0);
    expect(seg2Play.playback.isPlaying).toBe(true);
    expect(seg2Play.playback.stopAtTime).toBe(9.5);
    expect(seg2Play.activeSegmentId).toBe(2);

    // Exceeding block 2 endSec also pauses
    store.updatePlaybackTime(9.6);
    const seg2End = useDubDubStore.getState();
    expect(seg2End.playback.isPlaying).toBe(false);
    expect(seg2End.playback.stopAtTime).toBe(null);
  });

  test('ProjectDrawer renders Project Manager interface with Search, Select All, and items when open', () => {
    useDubDubStore.setState({
      drawerOpen: true,
      activeProjectId: 'proj_alpha',
      projectsList: [
        {
          id: 'proj_alpha',
          name: 'Alpha Dubbing Video',
          stage: 1,
          status: 'pending',
          duration: 12.5,
          createdAt: '2026-09-27T10:00:00Z',
          updatedAt: '2026-09-27T10:00:00Z',
        },
        {
          id: 'proj_beta',
          name: 'Beta Review Project',
          stage: 2,
          status: 'completed',
          duration: 45.0,
          createdAt: '2026-09-27T11:00:00Z',
          updatedAt: '2026-09-27T11:00:00Z',
        },
      ],
    });

    const html = renderToStaticMarkup(<ProjectDrawer />);

    // Header & Search
    expect(html).toContain('Project Manager');
    expect(html).toContain('Search projects by name, stage, or status');

    // Select All button and cards
    expect(html).toContain('data-testid="select-all-projects-btn"');
    expect(html).toContain('Select All (2)');
    expect(html).toContain('Alpha Dubbing Video');
    expect(html).toContain('Beta Review Project');
    expect(html).toContain('data-testid="checkbox-project-proj_alpha"');
    expect(html).toContain('data-testid="checkbox-project-proj_beta"');
    expect(html).toContain('data-testid="activate-project-proj_alpha"');
    expect(html).toContain('data-testid="delete-project-proj_alpha"');
    expect(html).toContain('Active');
    expect(html).toContain('Completed');
  });

  test('ProjectDrawer returns null when drawerOpen is false', () => {
    useDubDubStore.setState({
      drawerOpen: false,
      projectsList: [
        {
          id: 'p1',
          name: 'Hidden Project',
          stage: 1,
          status: 'pending',
          duration: 10,
          createdAt: '',
          updatedAt: '',
        },
      ],
    });

    const html = renderToStaticMarkup(<ProjectDrawer />);
    expect(html).toBe('');
  });

  test('deleteProjectsByIds successfully performs bulk deletion and cleans activeProjectId', async () => {
    const originalFetch = globalThis.fetch;
    let bulkDeletePayload: any = null;

    globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
      const urlStr = String(url);
      if (urlStr.includes('/api/projects/bulk-delete')) {
        bulkDeletePayload = JSON.parse((init?.body as string) || '{}');
        return new Response(JSON.stringify({ ok: true, deleted: bulkDeletePayload.ids, count: bulkDeletePayload.ids.length }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (urlStr.endsWith('/api/projects') && (!init?.method || init.method === 'GET')) {
        return new Response(JSON.stringify({
          projects: [
            {
              id: 'proj_gamma',
              name: 'Remaining Gamma Project',
              stage: 3,
              status: 'pending',
              duration: 30,
              createdAt: '',
              updatedAt: '',
            },
          ],
        }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response('{}', { status: 200 });
    }) as any;

    try {
      useDubDubStore.setState({
        activeProjectId: 'proj_alpha',
        projectsList: [
          { id: 'proj_alpha', name: 'Alpha', stage: 1, status: 'pending', duration: 10, createdAt: '', updatedAt: '' },
          { id: 'proj_beta', name: 'Beta', stage: 2, status: 'completed', duration: 20, createdAt: '', updatedAt: '' },
          { id: 'proj_gamma', name: 'Gamma', stage: 3, status: 'pending', duration: 30, createdAt: '', updatedAt: '' },
        ],
      });

      // Bulk delete proj_alpha and proj_beta
      await useDubDubStore.getState().deleteProjectsByIds(['proj_alpha', 'proj_beta']);

      // Verify payload sent
      expect(bulkDeletePayload).toEqual({ ids: ['proj_alpha', 'proj_beta'] });

      // Verify activeProjectId was cleared since active project was among deleted
      const updatedStore = useDubDubStore.getState();
      expect(updatedStore.activeProjectId).toBeNull();

      // Verify project list was reloaded
      expect(updatedStore.projectsList.length).toBe(1);
      expect(updatedStore.projectsList[0].id).toBe('proj_gamma');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('Stage 3 speaker filter accurately renders filter dropdown, counts, and pills', () => {
    useDubDubStore.setState({
      segments: [
        {
          id: 1,
          startSec: 0,
          endSec: 2,
          startTime: '00:00.000',
          endTime: '00:02.000',
          sourceText: 'Hello from speaker 1',
          targetText: 'Xin chao tu nguoi 1',
          speakerId: 'spk_1',
          speakerName: 'Speaker 1',
        },
        {
          id: 2,
          startSec: 2,
          endSec: 4,
          startTime: '00:02.000',
          endTime: '00:04.000',
          sourceText: 'Second line from speaker 1',
          targetText: 'Cau thu hai tu nguoi 1',
          speakerId: 'spk_1',
          speakerName: 'Speaker 1',
        },
        {
          id: 3,
          startSec: 4,
          endSec: 6,
          startTime: '00:04.000',
          endTime: '00:06.000',
          sourceText: 'Hello from speaker 2',
          targetText: 'Xin chao tu nguoi 2',
          speakerId: 'spk_2',
          speakerName: 'Speaker 2',
        },
      ],
      speakers: [
        { id: 'spk_1', name: 'Speaker 1', code: 'S1', color: 'amber' },
        { id: 'spk_2', name: 'Speaker 2', code: 'S2', color: 'purple' },
      ],
    });

    const html = renderToStaticMarkup(<Stage3VoiceDubbing />);

    // Speaker filter dropdown with total cues and counts
    expect(html).toContain('data-testid="stage3-speaker-filter"');
    expect(html).toContain('All Speakers (3)');
    expect(html).toContain('Speaker 1 (2)');
    expect(html).toContain('Speaker 2 (1)');

    // Interactive quick filter pills
    expect(html).toContain('data-testid="filter-pill-all"');
    expect(html).toContain('data-testid="filter-pill-spk_1"');
    expect(html).toContain('data-testid="filter-pill-spk_2"');
    expect(html).toContain('3 of 3 cues');
  });
});




