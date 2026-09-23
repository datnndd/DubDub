import { beforeEach, describe, expect, test } from 'bun:test';
import { renderToStaticMarkup } from 'react-dom/server';

import { Stage1Prepare } from '../src/screens/Stage1Prepare';
import { Stage2ReviewTranscript } from '../src/screens/Stage2ReviewTranscript';
import { Stage3VoiceDubbing } from '../src/screens/Stage3VoiceDubbing';
import { Stage4EditVideo } from '../src/screens/Stage4EditVideo';
import { useDubDubStore } from '../src/store';
import { buildPrepareJobRequest } from '../src/store/jobSlice';
import { buildTranslationRequest } from '../src/store/transcriptSlice';

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
});
