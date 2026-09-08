import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ScanText } from 'lucide-react';
import { Button, Dialog } from '../../ui';
import { API, apiJson } from '../../api/client';
import OcrRegionEditor from './OcrRegionEditor';
import OcrProgress from './OcrProgress';

export default function HardsubRegionDialog({
  open, onClose, jobId, videoUrl, running = false, progress,
  hasExistingSegments = false, result = null, onExtract, onCancel,
}) {
  const { t } = useTranslation();
  const [rect, setRect] = useState(null);
  const [modelId, setModelId] = useState('rapidocr');
  const [models, setModels] = useState([]);
  const [modelError, setModelError] = useState('');
  const [reload, setReload] = useState(0);
  useEffect(() => {
    if (!open) return;
    const ctrl = new AbortController();
    setModelError('');
    apiJson('/dub/hardsub-models', { signal: ctrl.signal }).then((data) => {
      setModels(data.models || []);
    }).catch((error) => {
      if (error.name !== 'AbortError') setModelError(error.message || t('common.error'));
    });
    return () => ctrl.abort();
  }, [open, reload, t]);
  useEffect(() => { if (open) setRect(null); }, [open, videoUrl, jobId]);
  const selected = models.find((model) => model.id === modelId);
  const start = () => {
    if (!rect || !selected || running) return;
    if (hasExistingSegments && !window.confirm(t('dub.hardsub_confirm'))) return;
    Promise.resolve(onExtract({ mode: 'ocr', model_id: modelId, crop: rect })).catch(() => {});
  };
  return <Dialog open={open} onClose={onClose} size="xl" dismissable={!running}
    title={t('dub.hardsub_dialog_title')}
    footer={<>
      {running ? <Button variant="danger" onClick={onCancel}>{t('dub.prep_stop')}</Button> : <>
        <Button variant="ghost" onClick={onClose}>{t('common.cancel')}</Button>
        <Button variant="primary" leading={<ScanText size={16} />} disabled={!rect || !selected || !!modelError} onClick={start}>
          {t('dub.hardsub_start')}
        </Button>
      </>}
    </>}>
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(260px,1fr)]">
      <OcrRegionEditor videoUrl={videoUrl || (jobId ? `${API}/dub/media/${jobId}` : undefined)}
        rect={rect} onChange={setRect} disabled={running} />
      <div className="min-w-0 space-y-4">
        <label className="block space-y-2 text-sm font-medium">
          <span>{t('ocr.model')}</span>
          <select value={modelId} disabled={running || !models.length}
            className="w-full rounded-md border border-border bg-background p-3 text-fg"
            onChange={(event) => setModelId(event.target.value)}>
            {!models.length && <option value="rapidocr">{t('common.loading')}</option>}
            {models.map((model) => <option key={model.id} value={model.id}>{model.label}{model.installed ? '' : ` · ${t('ocr.not_installed')}`}</option>)}
          </select>
        </label>
        <p className="text-sm text-fg-muted text-pretty">{t('ocr.local_hint')}</p>
        <p className="text-xs text-fg-muted text-pretty">{t('ocr.install_hint')}</p>
        {modelError && <div role="alert" className="space-y-2 text-sm text-[var(--color-danger)]">
          <p>{modelError}</p><Button variant="subtle" size="sm" onClick={() => setReload((n) => n + 1)}>{t('common.refresh')}</Button>
        </div>}
        {running && <OcrProgress progress={progress} />}
        {result?.error && <p role="alert" className="break-words text-sm text-[var(--color-danger)]">{result.error}</p>}
        {!running && <p className="text-sm text-fg-muted text-pretty">{t('ocr.review_hint')}</p>}
      </div>
    </div>
  </Dialog>;
}
