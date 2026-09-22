import { apiRequest } from './client';
import type { ProjectRecord } from '../types/project';

export async function fetchProjects(): Promise<ProjectRecord[]> {
  const data = await apiRequest<{ projects: ProjectRecord[] }>('/api/projects');
  return data.projects || [];
}

export async function fetchProject(id: string): Promise<ProjectRecord> {
  const data = await apiRequest<{ project: ProjectRecord }>(`/api/projects/${encodeURIComponent(id)}`);
  return data.project;
}

export async function createProject(payload: { name?: string; media_path?: string; state?: any }): Promise<ProjectRecord> {
  const data = await apiRequest<{ project: ProjectRecord }>('/api/projects', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return data.project;
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
