import { describe, expect, test } from 'bun:test';
import { buildRenderRequest } from '../src/store/editVideoSlice';

describe('React render request contract', () => {
  test('nests render settings and preserves uploaded asset and voice identifiers', () => {
    const request = buildRenderRequest({
      activeProjectId: 'project-1',
      backend: { mediaId: 'media-1', config: { ttsType: 2 } },
      editVideo: {
        audioMix: { original: 25, dubbed: 100, background: 40 },
        backgroundAudio: { id: 'bgm-1' },
        thumbnail: { id: 'thumb-1' },
      },
      subtitleStyles: { fontSize: 22 },
      segments: [{ id: 7, speakerId: 'speaker-1' }],
      speakerVoiceMap: { 'speaker-1': 'voice-a' },
      segmentVoiceOverrides: { 7: 'voice-b' },
    });

    expect(request).toEqual({
      mediaId: 'media-1',
      projectId: 'project-1',
      jobType: 'render',
      options: {
        ttsType: 2,
        audioMix: { original: 25, dubbed: 100, background: 40 },
        originalAudioVolume: 0.25,
        backgroundAudioVolume: 0.4,
        subtitleStyle: { fontSize: 22 },
        segments: [{ id: 7, speakerId: 'speaker-1' }],
        speakerVoiceMap: { 'speaker-1': 'voice-a' },
        segmentVoiceOverrides: { 7: 'voice-b' },
        backgroundAudioId: 'bgm-1',
        thumbnailId: 'thumb-1',
      },
    });
  });
});
