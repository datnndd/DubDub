/** Browser/server lifecycle view. Process supervision is outside the SPA. */
export type BackendLifecycleStage = 'ready' | 'starting' | 'failed' | 'unknown';

export interface BackendLifecycle {
  stage: BackendLifecycleStage;
  message: string | null;
}

export function classifyBootstrapStage(stage: string | null | undefined): BackendLifecycleStage {
  if (!stage) return 'unknown';
  if (stage === 'ready') return 'ready';
  if (stage === 'failed') return 'failed';
  return 'starting';
}

export function _toLifecycle(res: { stage?: string; message?: unknown } | null): BackendLifecycle {
  const stage = classifyBootstrapStage(res?.stage);
  if (stage !== 'failed') return { stage, message: null };
  const message = typeof res?.message === 'string' ? res.message.trim() : '';
  return { stage, message: message || null };
}

export async function backendLifecycleStage(): Promise<BackendLifecycle> {
  return { stage: 'unknown', message: null };
}
