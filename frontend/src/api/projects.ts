import { apiRequest } from './client';
import type { ProjectRecord } from '../types/project';

export async function fetchProjects(): Promise<ProjectRecord[]> {
  const data = await apiRequest<any>('/api/projects');
  return data?.projects || (Array.isArray(data) ? data : []);
}

export async function fetchProject(id: string): Promise<ProjectRecord> {
  const data = await apiRequest<any>(`/api/projects/${encodeURIComponent(id)}`);
  return data?.project || data;
}

export async function createProject(payload: {
  name?: string;
  media_path?: string;
  media_id?: string;
  mediaId?: string;
  duration?: number;
  stage?: number;
  state?: any;
}): Promise<ProjectRecord> {
  const data = await apiRequest<any>('/api/projects', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return data?.project || data;
}

export async function updateProjectState(id: string, state: any, stage?: number): Promise<void> {
  await apiRequest(`/api/projects/${encodeURIComponent(id)}`, {
    method: 'PUT',
    body: JSON.stringify({ state, stage }),
  });
}

export async function deleteProject(id: string): Promise<void> {
  await apiRequest(`/api/projects/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  });
}

export async function resumeProject(id: string): Promise<{ job_id: string }> {
  return apiRequest(`/api/projects/${encodeURIComponent(id)}/resume`, {
    method: 'POST',
  });
}
