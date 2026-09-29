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
});
