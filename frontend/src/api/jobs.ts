import { apiRequest } from './client';
import type { JobRecord, JobEvent } from '../types/job';

export async function fetchJob(id: string): Promise<JobRecord> {
  return apiRequest<JobRecord>(`/api/jobs/${encodeURIComponent(id)}`);
}

export async function cancelJob(id: string): Promise<void> {
  await apiRequest(`/api/jobs/${encodeURIComponent(id)}/cancel`, {
    method: 'POST',
  });
}

export async function startJob(payload: any): Promise<{ jobId: string }> {
  return apiRequest<{ jobId: string }>('/api/jobs', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function subscribeJobStream(
  jobId: string,
  afterSeq: number,
  onEvent: (event: JobEvent) => void,
  onError?: (err: any) => void
): () => void {
  const url = `/api/jobs/${encodeURIComponent(jobId)}/stream?after_seq=${afterSeq}`;
  const eventSource = new EventSource(url);

  eventSource.onmessage = (e) => {
    try {
      const data: JobEvent = JSON.parse(e.data);
      onEvent(data);
    } catch (err) {
      console.error('Failed to parse SSE event:', err);
    }
  };

  eventSource.onerror = (err) => {
    if (onError) onError(err);
  };

  return () => {
    eventSource.close();
  };
}
