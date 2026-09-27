import { apiRequest } from './client';

export interface ProviderStatus {
  id: string;
  name: string;
  category: string;
  configured: boolean;
  fromEnv: boolean;
  model?: string;
  models?: string[];
  baseUrl?: string;
  mirrorUrl?: string;
}

export interface StorageMetrics {
  paths: {
    output_dir: string;
    uploads_dir: string;
    models_dir: string;
    temp_dir: string;
  };
  usage: {
    output_dir_bytes: number;
    uploads_dir_bytes: number;
    models_dir_bytes: number;
    temp_dir_bytes: number;
    disk_total_bytes: number;
    disk_free_bytes: number;
    disk_used_bytes: number;
  };
}

export interface GeneralSettings {
  proxy: string;
  defaultSourceLanguage: string;
  defaultTargetLanguage: string;
  crf: number;
  preset: string;
}

export interface SettingsSnapshot {
  providers: Record<string, ProviderStatus>;
  storage: StorageMetrics;
  general: GeneralSettings;
}

export async function fetchSettings(): Promise<SettingsSnapshot> {
  return apiRequest('/api/settings');
}

export async function updateProviderSettings(
  category: string,
  providerId: string,
  payload: { apiKey?: string; model?: string; baseUrl?: string; mirrorUrl?: string }
): Promise<{ ok: boolean; configured: boolean; message: string }> {
  return apiRequest(`/api/settings/providers/${encodeURIComponent(category)}/${encodeURIComponent(providerId)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function testProviderConnection(
  category: string,
  providerId: string,
  payload?: { apiKey?: string; baseUrl?: string; proxy?: string }
): Promise<{ ok: boolean; message: string; models?: string[] }> {
  return apiRequest(`/api/settings/providers/${encodeURIComponent(category)}/${encodeURIComponent(providerId)}/test`, {
    method: 'POST',
    body: JSON.stringify(payload || {}),
  });
}

export async function fetchProviderModels(
  category: string,
  providerId: string,
  payload?: { apiKey?: string; baseUrl?: string; proxy?: string }
): Promise<{ ok: boolean; providerId: string; models: string[]; message: string }> {
  return apiRequest(`/api/settings/providers/${encodeURIComponent(category)}/${encodeURIComponent(providerId)}/models`, {
    method: 'POST',
    body: JSON.stringify(payload || {}),
  });
}

export async function fetchStorageSettings(): Promise<StorageMetrics> {
  return apiRequest('/api/settings/storage');
}

export async function updateStorageSettings(
  paths: Partial<StorageMetrics['paths']>
): Promise<{ ok: boolean; storage: StorageMetrics; message: string }> {
  return apiRequest('/api/settings/storage', {
    method: 'PUT',
    body: JSON.stringify(paths),
  });
}

export async function cleanTempCache(): Promise<{ ok: boolean; cleaned_bytes: number; cleaned_files: number }> {
  return apiRequest('/api/settings/storage/clean-temp', {
    method: 'POST',
  });
}

export async function updateGeneralSettings(
  general: Partial<GeneralSettings>
): Promise<{ ok: boolean; message: string }> {
  return apiRequest('/api/settings/general', {
    method: 'PUT',
    body: JSON.stringify(general),
  });
}
