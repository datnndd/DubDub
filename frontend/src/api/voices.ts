import { apiRequest } from './client';

export interface CustomVoice {
  id: string;
  name: string;
  description?: string;
  provider: number;
  kind?: string;
  language?: string;
  ref_audio_path?: string;
  ref_text?: string;
  instruct?: string;
  external_voice_id?: string;
  tuning_params?: Record<string, any>;
  preview_audio_path?: string;
  is_active?: boolean;
  created_at?: number;
  updated_at?: number;
}

export interface CreateVoicePayload {
  name: string;
  provider?: number | string;
  description?: string;
  language?: string;
  kind?: string;
  ref_text?: string;
  instruct?: string;
  audio?: Blob | File;
  external_voice_id?: string;
  tuning_params?: Record<string, any>;
}

export async function fetchCustomVoices(provider?: number): Promise<CustomVoice[]> {
  const url = provider !== undefined ? `/api/custom-voices?provider=${provider}` : '/api/custom-voices';
  const data = await apiRequest<{ voices: CustomVoice[] }>(url);
  return data.voices || [];
}

export async function fetchCustomVoice(id: string): Promise<CustomVoice> {
  return apiRequest<CustomVoice>(`/api/custom-voices/${encodeURIComponent(id)}`);
}

export async function createCustomVoice(payload: CreateVoicePayload): Promise<CustomVoice> {
  const formData = new FormData();
  formData.append('name', payload.name);
  if (payload.provider !== undefined) formData.append('provider', String(payload.provider));
  if (payload.description) formData.append('description', payload.description);
  if (payload.language) formData.append('language', payload.language);
  if (payload.kind) formData.append('kind', payload.kind);
  if (payload.ref_text) formData.append('ref_text', payload.ref_text);
  if (payload.instruct) formData.append('instruct', payload.instruct);
  if (payload.external_voice_id) formData.append('external_voice_id', payload.external_voice_id);
  if (payload.tuning_params) formData.append('tuning_params', JSON.stringify(payload.tuning_params));
  if (payload.audio) {
    let filename = 'recording.wav';
    if (payload.audio instanceof File) {
      filename = payload.audio.name;
    } else if (payload.audio.type) {
      if (payload.audio.type.includes('webm')) filename = 'recording.webm';
      else if (payload.audio.type.includes('mp4') || payload.audio.type.includes('m4a')) filename = 'recording.mp4';
      else if (payload.audio.type.includes('ogg')) filename = 'recording.ogg';
      else if (payload.audio.type.includes('flac')) filename = 'recording.flac';
    }
    formData.append('audio', payload.audio, filename);
  }

  return apiRequest<CustomVoice>('/api/custom-voices', {
    method: 'POST',
    body: formData,
  });
}

export async function updateCustomVoice(id: string, updates: Partial<CustomVoice>): Promise<CustomVoice> {
  return apiRequest<CustomVoice>(`/api/custom-voices/${encodeURIComponent(id)}`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
}

export async function deleteCustomVoice(id: string, hard: boolean = false): Promise<{ ok: boolean; id: string }> {
  return apiRequest<{ ok: boolean; id: string }>(`/api/custom-voices/${encodeURIComponent(id)}${hard ? '?hard=true' : ''}`, {
    method: 'DELETE',
  });
}

export async function previewCustomVoice(id: string, text?: string, language?: string): Promise<{ ok: boolean; preview_url: string }> {
  return apiRequest<{ ok: boolean; preview_url: string }>(`/api/custom-voices/${encodeURIComponent(id)}/preview`, {
    method: 'POST',
    body: JSON.stringify({ text, language }),
  });
}

export function getCustomVoiceAudioUrl(id: string): string {
  return `/api/custom-voices/${encodeURIComponent(id)}/audio`;
}

export function getCustomVoicePreviewAudioUrl(id: string): string {
  return `/api/custom-voices/${encodeURIComponent(id)}/preview/audio`;
}
