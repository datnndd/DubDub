import { apiJson, apiPost } from './client';

export async function listExportHistory(): Promise<unknown> {
  return apiJson('/export/history');
}

export async function exportRecord(body: Record<string, unknown>): Promise<unknown> {
  return apiPost('/export/record', body);
}
