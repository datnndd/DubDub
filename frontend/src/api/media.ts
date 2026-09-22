import { apiRequest } from './client';

export async function uploadMedia(file: File): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);
  return apiRequest('/api/media', {
    method: 'POST',
    body: formData,
  });
}

export async function uploadEditAsset(kind: 'background-audio' | 'thumbnail', file: File): Promise<{ id: string; name: string }> {
  const formData = new FormData();
  formData.append('file', file);
  return apiRequest(`/api/assets/${kind}`, {
    method: 'POST',
    body: formData,
  });
}
