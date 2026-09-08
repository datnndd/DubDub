import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { formatOcrTime } from '../../utils/ocrRegion';

const stages = new Set(['uploading', 'preparing', 'bootstrap', 'sampling', 'loading', 'ocr', 'refine', 'saving']);
const stageAliases = { sampling: 'preparing', loading: 'bootstrap' };

export default function OcrProgress({ progress }) {
  const { t } = useTranslation();
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const stage = stages.has(progress?.stage) ? progress.stage : 'bootstrap';
  const stageLabel = stage === 'saving' ? t('common.saving') : t(`ocr.stage_${stageAliases[stage] || stage}`);
  const percent = Number.isFinite(progress?.percent) && progress.percent >= 0 ? Math.min(100, progress.percent) : undefined;
  const elapsed = progress?.startedAt ? Math.max(0, (now - progress.startedAt) / 1000) : 0;
  const eta = stage === 'ocr' && progress.framesDone >= 2 && Number.isFinite(progress.etaSeconds) ? progress.etaSeconds : null;
  return <section className="space-y-4 rounded-lg border border-border p-4" aria-label={t('ocr.progress')}>
    <div className="flex justify-between gap-3 text-sm font-medium" role="status">
      <span>{stageLabel}</span><span className="tabular-nums">{percent == null ? '—' : `${Math.round(percent)}%`}</span>
    </div>
    <progress max="100" value={percent} aria-label={t('ocr.progress')} className="h-2 w-full accent-[var(--color-brand)]" />
    <div className="grid grid-cols-2 gap-4 text-sm tabular-nums">
      <p>{t('ocr.elapsed', { value: formatOcrTime(elapsed) })}</p>
      <p>{eta == null ? t('ocr.estimating') : t('ocr.eta', { value: formatOcrTime(eta) })}</p>
    </div>
    {stage === 'ocr' && <>
      <p className="text-xs text-fg-muted tabular-nums">{t('ocr.frames', { done: progress.framesDone || 0, total: progress.framesTotal || 0 })} · {formatOcrTime(progress.videoTime)}</p>
      {Number.isFinite(progress.ocrCalls) && Number.isFinite(progress.skippedFrames) &&
        <p className="text-xs text-fg-muted tabular-nums">{t('ocr.inference_counts', { calls: progress.ocrCalls, skipped: progress.skippedFrames })}</p>}
      <div className="space-y-2 border-t border-border pt-3">
        <p className="text-xs font-medium text-fg-muted">{t('ocr.live_text')}</p>
        <p className="max-h-32 overflow-auto whitespace-pre-wrap break-words text-sm" data-testid="ocr-live-text">{progress.currentText || '—'}</p>
      </div>
    </>}
  </section>;
}
