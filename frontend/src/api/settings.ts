import { apiRequest } from './client';

export async function fetchOptions(): Promise<any> {
  return apiRequest('/api/options');
}

export async function fetchVoices(ttsType: number = 2): Promise<any[]> {
  const data = await apiRequest<{ voices: any[] }>(`/api/voices?tts_type=${ttsType}`);
  return data.voices || [];
}

export async function saveAsrSettings(providerId: string, apiKey: string): Promise<any> {
  return apiRequest(`/api/asr-settings/${encodeURIComponent(providerId)}`, {
    method: 'POST',
    body: JSON.stringify({ apiKey }),
  });
}

export async function testAsrProvider(recognType: number, modelName: string): Promise<{ ok: boolean; message: string }> {
  return apiRequest('/api/test/asr', {
    method: 'POST',
    body: JSON.stringify({ recognType, modelName }),
  });
}

export async function testTranslationProvider(translateType: number, useCuda: boolean = false): Promise<{ ok: boolean; message: string }> {
  return apiRequest('/api/test/translation', {
    method: 'POST',
    body: JSON.stringify({ translateType, useCuda }),
  });
}
