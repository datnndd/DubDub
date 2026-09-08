import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '../../ui';
import { formatOcrTime } from '../../utils/ocrRegion';

/** Review source text before any translation. Edits are committed on Continue. */
export default function OcrPrepareReview({ segments, videoUrl, onContinue, onRescan }) {
  const { t } = useTranslation();
  const videoRef = useRef(null);
  const [draft, setDraft] = useState(() => segments.map((seg) => ({ ...seg })));
  const [page, setPage] = useState(0);
  const pageSize = 30;
  const pages = Math.max(1, Math.ceil(draft.length / pageSize));
  const valid = draft.length > 0 && draft.every((seg) => seg.text.trim());
  return <section className="flex min-h-0 flex-1 flex-col gap-5 p-4 sm:p-6" aria-label={t('ocr.review_title')}>
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div><h2 className="text-xl font-semibold text-balance">{t('dub.phase_prepare')} · {t('ocr.review_title')}</h2>
        <p className="mt-1 text-sm text-fg-muted text-pretty">{t('ocr.review_hint')}</p></div>
      <div className="flex gap-2"><Button variant="subtle" onClick={onRescan}>{t('dub.hardsub_btn')}</Button>
        <Button variant="primary" disabled={!valid} onClick={() => onContinue(draft)}>{t('ocr.continue')}</Button></div>
    </header>
    <div className="grid min-h-0 flex-1 items-start gap-5 lg:grid-cols-2">
      <video ref={videoRef} src={videoUrl} controls preload="metadata" className="w-full max-h-[60vh] rounded-lg bg-black" />
      <div className="min-w-0 space-y-3">
        <p className="text-sm text-fg-muted">{t('dub.hardsub_result_done', { count: draft.length })}</p>
        <div className="max-h-[55vh] space-y-3 overflow-auto rounded-lg border border-border p-3">
          {draft.slice(page * pageSize, (page + 1) * pageSize).map((seg, index) => <div key={seg.id} className="space-y-2">
            <button type="button" className="text-xs text-fg-muted tabular-nums underline"
              onClick={() => { videoRef.current.currentTime = seg.start; }}>
              {page * pageSize + index + 1}. {formatOcrTime(seg.start)} → {formatOcrTime(seg.end)}
            </button>
            <textarea aria-label={t('ocr.cue', { number: page * pageSize + index + 1 })}
              rows={2} value={seg.text} className="block w-full resize-y rounded-md border border-border bg-background p-2 text-sm text-fg"
              onChange={(e) => setDraft((prev) => prev.map((row) => row.id === seg.id ? { ...row, text: e.target.value } : row))} />
          </div>)}
        </div>
        {!valid && <p role="alert" className="text-sm text-[var(--color-danger)]">{t('ocr.empty_cue')}</p>}
        {pages > 1 && <div className="flex justify-between gap-3">
          <Button variant="subtle" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)} aria-label={t('ocr.previous')}>←</Button>
          <span className="text-sm tabular-nums">{page + 1} / {pages}</span>
          <Button variant="subtle" size="sm" disabled={page === pages - 1} onClick={() => setPage(page + 1)} aria-label={t('ocr.next')}>→</Button>
        </div>}
      </div>
    </div>
  </section>;
}
