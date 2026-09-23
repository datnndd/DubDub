import { apiRequest } from './client';

export async function requestTranslate(payload: {
  segments: any[];
  sourceLanguage: string;
  targetLanguage: string;
  translateType: number;
  translationMode?: string;
}): Promise<{ ok: boolean; segments: any[] }> {
  return apiRequest('/api/translate', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function requestOcrExtract(payload: {
  mediaId: string;
  roi: [number, number, number, number];
  startSec: number;
  endSec: number;
  segmentId?: number;
}): Promise<{ ok: boolean; text: string; confidence?: number; boxNumber?: string }> {
  return apiRequest('/api/ocr/extract', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function requestSplitSegment(payload: {
  segment: any;
  splitSec: number;
}): Promise<{ ok: boolean; segments: any[] }> {
  return apiRequest('/api/segments/split', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function requestRender(payload: any): Promise<{ id?: string; jobId?: string }> {
  return apiRequest('/api/render', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
