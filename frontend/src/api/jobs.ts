import { apiRequest } from './client';

export async function fetchJob(id: string): Promise<any> {
  return apiRequest(`/api/jobs/${encodeURIComponent(id)}`);
}

export async function cancelJob(id: string): Promise<void> {
  await apiRequest(`/api/jobs/${encodeURIComponent(id)}/cancel`, {
    method: 'POST',
  });
}

export async function startJob(payload: any): Promise<{ id: string; jobId?: string; [key: string]: any }> {
  return apiRequest('/api/jobs', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function subscribeJobStream(
  jobId: string,
  afterSeq: number,
  onEvent: (event: any) => void,
  onDone?: (event: any) => void,
  onError?: (err: any) => void
): () => void {
  const url = `/api/jobs/${encodeURIComponent(jobId)}/stream?after_seq=${afterSeq}`;
  const eventSource = new EventSource(url);

  eventSource.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      onEvent(data);
    } catch (err) {
      console.error('Failed to parse SSE event:', err);
    }
  };

  eventSource.addEventListener('done', (e: any) => {
    try {
      const data = JSON.parse(e.data);
      if (onDone) onDone(data);
      else onEvent(data);
    } catch (_) {}
    eventSource.close();
  });

  eventSource.onerror = (err) => {
    if (onError) onError(err);
  };

  return () => {
    eventSource.close();
  };
}
