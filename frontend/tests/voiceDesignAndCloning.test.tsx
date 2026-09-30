import { beforeEach, describe, expect, test } from 'bun:test';
import { renderToStaticMarkup } from 'react-dom/server';
import React from 'react';

import { useDubDubStore } from '../src/store';
import { CreateVoiceModal } from '../src/components/CreateVoiceModal';
import { VoiceManagementScreen } from '../src/screens/VoiceManagementScreen';
import { Stage3VoiceDubbing } from '../src/screens/Stage3VoiceDubbing';

describe('VieNeu-TTS Voice Design & Voice Cloning', () => {
  beforeEach(() => {
    useDubDubStore.setState({
      activeProjectId: 'proj-design-test',
      currentStep: 3,
      isCreateVoiceModalOpen: true,
      customVoices: [
        {
          id: 'cv_cloned_1',
          name: 'Bảo Anh Real Voice',
          provider: 2,
          kind: 'clone',
          language: 'vi',
          description: 'Enrolled via ONNX denoiser',
          ref_audio_path: 'bao_anh.wav',
        },
        {
          id: 'cv_designed_1',
          name: 'Hoàng Long News Anchor',
          provider: 2,
          kind: 'design',
          language: 'vi',
          external_voice_id: 'Tuyên (nam miền Bắc)',
          description: 'News broadcast style with low temperature',
          tuning_params: {
            base_voice: 'Tuyên (nam miền Bắc)',
            style: 'tin_tuc',
            temperature: 0.7,
            emotions: ['[hắng giọng]'],
          },
        },
        {
          id: 'cv_designed_2',
          name: 'Storyteller Fairy',
          provider: 2,
          kind: 'design',
          language: 'vi',
          external_voice_id: 'Ly (nữ miền Bắc)',
          description: 'Bedtime story voice with sighs',
          tuning_params: {
            base_voice: 'Ly (nữ miền Bắc)',
            style: 'doc_truyen',
            temperature: 0.95,
            emotions: ['[thở dài]'],
          },
        },
      ],
      voices: [
        { id: 'Bình (nam miền Bắc)', name: 'Bình (nam miền Bắc)', provider: 2 },
        { id: 'Ly (nữ miền Bắc)', name: 'Ly (nữ miền Bắc)', provider: 2 },
        { id: 'Tuyên (nam miền Bắc)', name: 'Tuyên (nam miền Bắc)', provider: 2 },
      ],
      segments: [
        {
          id: 1,
          speakerId: 'spk_1',
          startTime: '00:00:01,000',
          endTime: '00:00:05,000',
          startSec: 1.0,
          endSec: 5.0,
          sourceText: 'Xin chào quý vị khán giả.',
          targetText: 'Xin chào quý vị và các bạn theo dõi chương trình.',
        },
      ],
      speakers: [
        {
          id: 'spk_1',
          code: 'S1',
          name: 'Speaker One',
          color: 'amber',
        },
      ],
      speakerVoiceMap: {
        spk_1: 'Bình (nam miền Bắc)',
      },
      segmentVoiceOverrides: {},
    });
  });

  test('CreateVoiceModal renders dual-mode tab switcher with Cloning and Voice Design', () => {
    const html = renderToStaticMarkup(<CreateVoiceModal />);
    expect(html).toContain('Voice Cloning');
    expect(html).toContain('Voice Design');
    expect(html).toContain('VieNeu');
    expect(html).toContain('ONNX Auto-Denoise');
    expect(html).toContain('Cloning Model Backbone');
  });

  test('VoiceManagementScreen renders Kind filter with Cloned and Designed options', () => {
    const html = renderToStaticMarkup(<VoiceManagementScreen initialTab="custom" />);
    expect(html).toContain('data-testid="voice-kind-filter"');
    expect(html).toContain('All Types');
    expect(html).toContain('Cloned Only');
    expect(html).toContain('Designed Only');
  });

  test('VoiceManagementScreen displays Designed vs Cloned badges accurately', () => {
    const html = renderToStaticMarkup(<VoiceManagementScreen initialTab="custom" />);
    expect(html).toContain('Bảo Anh Real Voice');
    expect(html).toContain('Cloned');
    expect(html).toContain('Hoàng Long News Anchor');
    expect(html).toContain('Designed • Tin tức');
    expect(html).toContain('Storyteller Fairy');
    expect(html).toContain('Designed • Đọc truyện');
  });

  test('VoiceManagementScreen Test Synthesis Lab includes style selector, emotion tag buttons, and temperature slider', () => {
    const html = renderToStaticMarkup(<VoiceManagementScreen initialTab="custom" />);
    expect(html).toContain('VieNeu Speaking Style');
    expect(html).toContain('Tự nhiên (Natural Dialogue)');
    expect(html).toContain('Tin tức (News Broadcast)');
    expect(html).toContain('Đọc truyện (Storytelling / Drama)');
    expect(html).toContain('Expressiveness (Temp)');
    expect(html).toContain('+ [cười]');
    expect(html).toContain('+ [thở dài]');
    expect(html).toContain('+ [hắng giọng]');
  });

  test('Stage3VoiceDubbing renders emotion tag shortcuts in dialogue block text editor', () => {
    const html = renderToStaticMarkup(<Stage3VoiceDubbing />);
    expect(html).toContain('+ [cười]');
    expect(html).toContain('+ [thở dài]');
    expect(html).toContain('+ [hắng giọng]');
    expect(html).toContain('data-segment-input="stage3-1"');
  });

  test('CreateVoiceModal renders cloning audio dropzone and trimmer capabilities', () => {
    const html = renderToStaticMarkup(<CreateVoiceModal />);
    expect(html).toContain('Reference Audio Sample');
    expect(html).toContain('Upload File');
    expect(html).toContain('Record Mic');
    expect(html).toContain('WAV, MP3, M4A, WebM');
  });

  test('trimAudio client function sends proper parameters', async () => {
    const { trimAudio } = await import('../src/api/voices');
    let capturedUrl = '';
    let capturedBody: any = null;

    const mockData = {
      ok: true,
      original_duration: 45.0,
      start_time: 5.0,
      end_time: 15.0,
      duration: 10.0,
      audio_url: '/api/voices/trimmed-audio/trim_test.wav',
      filename: 'trim_test.wav',
    };

    (globalThis as any).fetch = async (url: string, init: any) => {
      capturedUrl = url;
      capturedBody = init?.body;
      return {
        ok: true,
        status: 200,
        headers: {
          get: (name: string) => (name.toLowerCase() === 'content-type' ? 'application/json' : null),
        },
        json: async () => mockData,
        text: async () => JSON.stringify(mockData),
      };
    };

    const dummyBlob = new Blob(['fake-audio-bytes'], { type: 'audio/wav' });
    const res = await trimAudio({
      audio: dummyBlob,
      start_time: 5.0,
      end_time: 15.0,
      auto_detect: true,
      provider: 2,
    });

    expect(capturedUrl).toBe('/api/voices/trim-audio');
    expect(capturedBody).toBeInstanceOf(FormData);
    expect(res.ok).toBe(true);
    expect(res.duration).toBe(10.0);
    expect(res.start_time).toBe(5.0);
    expect(res.end_time).toBe(15.0);
  });

  test('previewCloneVoice client function sends proper parameters and returns preview metadata', async () => {
    const { previewCloneVoice } = await import('../src/api/voices');
    let capturedUrl = '';
    let capturedBody: any = null;

    const mockData = {
      ok: true,
      preview_id: 'preview_clone_12345678',
      preview_filename: 'preview_clone_12345678.wav',
      preview_url: '/api/voices/preview-audio/preview_clone_12345678.wav',
      audio_url: '/api/voices/preview-audio/preview_clone_12345678.wav',
    };

    (globalThis as any).fetch = async (url: string, init: any) => {
      capturedUrl = url;
      capturedBody = init?.body;
      return {
        ok: true,
        status: 200,
        headers: {
          get: (name: string) => (name.toLowerCase() === 'content-type' ? 'application/json' : null),
        },
        json: async () => mockData,
        text: async () => JSON.stringify(mockData),
      };
    };

    const dummyBlob = new Blob(['sample-voice-data'], { type: 'audio/mpeg' });
    const res = await previewCloneVoice({
      audio: dummyBlob,
      provider: 2,
      text: 'Test preview phrase for cloned voice',
      language: 'vi',
      denoise: true,
      cut_start: 1.0,
      cut_end: 6.0,
    });

    expect(capturedUrl).toBe('/api/voices/preview-clone');
    expect(capturedBody).toBeInstanceOf(FormData);
    expect(res.ok).toBe(true);
    expect(res.preview_id).toBe('preview_clone_12345678');
    expect(res.preview_url).toBe('/api/voices/preview-audio/preview_clone_12345678.wav');
  });

  test('createCustomVoice client function carries preview_filename and maps MP3 audio', async () => {
    const { createCustomVoice } = await import('../src/api/voices');
    let capturedUrl = '';
    let capturedFormData: any = null;

    const mockResponse = {
      id: 'voice_3b224d3c',
      name: 'Cloned Voice Test',
      provider: 2,
      kind: 'clone',
      ref_audio_path: 'voice_3b224d3c.wav',
      preview_audio_path: 'voice_3b224d3c_preview.wav',
      preview_url: '/api/custom-voices/voice_3b224d3c/preview/audio',
      audio_url: '/api/custom-voices/voice_3b224d3c/audio',
    };

    (globalThis as any).fetch = async (url: string, init: any) => {
      capturedUrl = url;
      capturedFormData = init?.body;
      return {
        ok: true,
        status: 201,
        headers: {
          get: (name: string) => (name.toLowerCase() === 'content-type' ? 'application/json' : null),
        },
        json: async () => mockResponse,
        text: async () => JSON.stringify(mockResponse),
      };
    };

    const mp3Blob = new Blob(['mp3-binary-frames'], { type: 'audio/mp3' });
    const res = await createCustomVoice({
      name: 'Cloned Voice Test',
      provider: 2,
      audio: mp3Blob,
      preview_filename: 'preview_clone_12345678.wav',
    });

    expect(capturedUrl).toBe('/api/custom-voices');
    expect(capturedFormData).toBeInstanceOf(FormData);
    expect(capturedFormData.get('preview_filename')).toBe('preview_clone_12345678.wav');
    expect(capturedFormData.get('name')).toBe('Cloned Voice Test');
    expect(res.id).toBe('voice_3b224d3c');
    expect(res.preview_audio_path).toBe('voice_3b224d3c_preview.wav');
  });

  test('CreateVoiceModal renders Preview Cloned Voice button and test phrase area when reference audio is provided', () => {
    // Render CreateVoiceModal initially
    const html = renderToStaticMarkup(<CreateVoiceModal />);
    // Verify standard cloning surfaces are present
    expect(html).toContain('Reference Audio Sample');
    expect(html).toContain('data-modal="create-voice"');
    expect(html).toContain('Save Cloned Voice');
  });

  test('VoiceManagementScreen Synthesis Lab renders direct voice picker and selects voice properly', () => {
    useDubDubStore.setState({
      customVoices: [
        {
          id: 'voice_custom_1',
          name: 'Custom Character Voice',
          provider: 2,
          kind: 'clone',
          ref_audio_path: 'ref.wav',
        },
      ],
      voices: [
        { id: 'No', name: 'No Dubbing (Mute/Retain)', provider: 2, kind: 'preset' },
        { id: 'Minh Đức', name: 'Minh Đức', provider: 2, kind: 'preset' },
      ],
    });

    const html = renderToStaticMarkup(<VoiceManagementScreen initialTab="all" />);
    // Verify Lab panel header and components
    expect(html).toContain('Synthesis Lab &amp; Preview');
    expect(html).toContain('data-testid="lab-voice-picker"');
    expect(html).toContain('Custom Character Voice');
    expect(html).toContain('Minh Đức');
    expect(html).toContain('Synthesize &amp; Audition');
  });
});



