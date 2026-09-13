import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ScanText, Crop } from 'lucide-react';
import { Button, Dialog } from '../../ui';
import { formatOcrTime } from '../../utils/ocrRegion';
import OcrRegionEditor from './OcrRegionEditor';
import toast from 'react-hot-toast';
import { cn } from '../../lib/utils';

/** Review source text before any translation. Edits are committed on Continue. */
export default function OcrPrepareReview({
  segments = [],
  videoUrl,
  onContinue,
  onRescan,
  onReplaceWithOcr,
}) {
  const { t } = useTranslation();
  const videoRef = useRef(null);
  const [draft, setDraft] = useState(() => segments.map((seg) => ({ ...seg })));
  const [page, setPage] = useState(0);
  const pageSize = 30;
  const pages = Math.max(1, Math.ceil(draft.length / pageSize));
  const valid = draft.length > 0 && draft.every((seg) => seg.text.trim());

  // Row selection state
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [isReplacing, setIsReplacing] = useState(false);

  // Subtitle crop region state
  const [savedCrop, setSavedCrop] = useState(null);
  const [cropModalOpen, setCropModalOpen] = useState(false);
  const [tempCrop, setTempCrop] = useState(null);
  const pendingReplaceRef = useRef(null);

  const toggleSelect = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const allSelected = draft.length > 0 && draft.every((s) => selectedIds.has(s.id));
  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(draft.map((s) => s.id)));
    }
  };

  const executeOcrReplace = async (crop) => {
    const selectedSegs = draft.filter((s) => selectedIds.has(s.id));
    if (selectedSegs.length === 0) return;

    setIsReplacing(true);
    try {
      const rawRanges = selectedSegs.map((s) => [s.start, s.end]);
      rawRanges.sort((a, b) => a[0] - b[0]);
      const mergedRanges = [rawRanges[0]];
      for (let i = 1; i < rawRanges.length; i++) {
        const [curS, curE] = rawRanges[i];
        const prev = mergedRanges[mergedRanges.length - 1];
        if (curS <= prev[1] + 0.5) {
          prev[1] = Math.max(prev[1], curE);
        } else {
          mergedRanges.push([curS, curE]);
        }
      }

      const res = await onReplaceWithOcr?.({
        time_ranges: mergedRanges,
        crop,
        model_id: 'rapidocr',
      });

      const newCues = (res && res.segments) || [];
      if (newCues.length > 0) {
        const spkId = selectedSegs[0]?.speaker_id ?? selectedSegs[0]?.speaker;
        const normalizedCues = newCues.map((c, i) => ({
          ...c,
          id: `ocr_${Date.now()}_${i}`,
          speaker_id: spkId,
          speaker: spkId,
        }));
        const remaining = draft.filter((s) => !selectedIds.has(s.id));
        const merged = [...remaining, ...normalizedCues].sort((a, b) => a.start - b.start);
        setDraft(merged);
        toast.success(
          t('ocr.replaced_count', {
            count: newCues.length,
            defaultValue: `Replaced with ${newCues.length} OCR cues`,
          }),
        );
      } else {
        setDraft((prev) =>
          prev.map((row) => (selectedIds.has(row.id) ? { ...row, text: '' } : row)),
        );
        toast(
          t('ocr.no_text_cleared', {
            defaultValue: 'No text detected by OCR. Row text cleared for manual entry.',
          }),
        );
      }
      setSelectedIds(new Set());
    } catch (err) {
      toast.error(
        err?.message ||
          t('ocr.replace_failed', { defaultValue: 'Failed to replace with OCR' }),
      );
    } finally {
      setIsReplacing(false);
    }
  };

  const handleReplaceClick = () => {
    if (selectedIds.size === 0 || isReplacing) return;
    if (!savedCrop) {
      pendingReplaceRef.current = (crop) => executeOcrReplace(crop);
      setTempCrop({ left: 0.05, top: 0.7, right: 0.95, bottom: 0.95 });
      setCropModalOpen(true);
      return;
    }
    executeOcrReplace(savedCrop);
  };

  const handleAdjustRegion = () => {
    setTempCrop(savedCrop || { left: 0.05, top: 0.7, right: 0.95, bottom: 0.95 });
    pendingReplaceRef.current = null;
    setCropModalOpen(true);
  };

  return (
    <section className="flex min-h-0 flex-1 flex-col gap-5 p-4 sm:p-6" aria-label={t('ocr.review_title')}>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-balance">
            {t('dub.phase_prepare')} · {t('ocr.review_title')}
          </h2>
          <p className="mt-1 text-sm text-fg-muted text-pretty">{t('ocr.review_hint')}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {onRescan && (
            <Button variant="subtle" onClick={onRescan}>
              {t('dub.hardsub_btn')}
            </Button>
          )}
          <Button variant="primary" disabled={!valid} onClick={() => onContinue(draft)}>
            {t('ocr.continue')}
          </Button>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 items-start gap-5 lg:grid-cols-2">
        <video
          ref={videoRef}
          src={videoUrl}
          controls
          preload="metadata"
          className="w-full max-h-[60vh] rounded-lg bg-black"
        />
        <div className="min-w-0 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-2">
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-1.5 text-xs text-fg-muted cursor-pointer">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleSelectAll}
                  className="rounded border-border"
                  title={t('ocr.select_all', { defaultValue: 'Select All' })}
                />
                <span>{t('ocr.select_all', { defaultValue: 'Select All' })}</span>
              </label>
              {selectedIds.size > 0 && (
                <span className="text-xs text-fg-muted font-medium">
                  {t('ocr.selected_count', { count: selectedIds.size, defaultValue: `${selectedIds.size} selected` })}
                </span>
              )}
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                leading={<Crop size={14} />}
                onClick={handleAdjustRegion}
                title={t('ocr.adjust_region', { defaultValue: 'Adjust OCR Region' })}
              >
                {t('ocr.adjust_region', { defaultValue: 'Adjust OCR Region' })}
              </Button>
              {selectedIds.size > 0 && (
                <Button
                  variant="secondary"
                  size="sm"
                  loading={isReplacing}
                  disabled={isReplacing}
                  leading={<ScanText size={14} />}
                  onClick={handleReplaceClick}
                >
                  {t('ocr.replace_with_ocr', { defaultValue: 'Replace with OCR' })}
                </Button>
              )}
            </div>
          </div>

          <p className="text-sm text-fg-muted">
            {t('dub.hardsub_result_done', { count: draft.length })}
          </p>

          <div className="max-h-[55vh] space-y-3 overflow-auto rounded-lg border border-border p-3">
            {draft.slice(page * pageSize, (page + 1) * pageSize).map((seg, index) => {
              const isSelected = selectedIds.has(seg.id);
              const rowNum = page * pageSize + index + 1;
              return (
                <div
                  key={seg.id}
                  className={cn(
                    'space-y-2 rounded-md p-2 transition-colors border',
                    isSelected
                      ? 'bg-[var(--color-brand)]/5 border-[var(--color-brand)]/40 shadow-sm'
                      : 'border-transparent hover:border-border',
                  )}
                >
                  <div className="flex items-center justify-between">
                    <label className="flex items-center gap-2 cursor-pointer text-xs text-fg-muted">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleSelect(seg.id)}
                        className="rounded border-border"
                        aria-label={t('ocr.select_row', { number: rowNum, defaultValue: `Select row ${rowNum}` })}
                      />
                      <button
                        type="button"
                        className="tabular-nums underline hover:text-fg"
                        onClick={() => {
                          if (videoRef.current) videoRef.current.currentTime = seg.start;
                        }}
                      >
                        {rowNum}. {formatOcrTime(seg.start)} → {formatOcrTime(seg.end)}
                      </button>
                    </label>
                    {seg.speaker_id && (
                      <span className="text-[11px] text-fg-muted font-mono rounded px-1.5 py-0.5 bg-muted">
                        {seg.speaker_id}
                      </span>
                    )}
                  </div>
                  <textarea
                    aria-label={t('ocr.cue', { number: rowNum })}
                    rows={2}
                    value={seg.text}
                    className="block w-full resize-y rounded-md border border-border bg-background p-2 text-sm text-fg"
                    onChange={(e) =>
                      setDraft((prev) =>
                        prev.map((row) => (row.id === seg.id ? { ...row, text: e.target.value } : row)),
                      )
                    }
                  />
                </div>
              );
            })}
          </div>

          {!valid && <p role="alert" className="text-sm text-[var(--color-danger)]">{t('ocr.empty_cue')}</p>}

          {pages > 1 && (
            <div className="flex justify-between gap-3">
              <Button
                variant="subtle"
                size="sm"
                disabled={page === 0}
                onClick={() => setPage(page - 1)}
                aria-label={t('ocr.previous')}
              >
                ←
              </Button>
              <span className="text-sm tabular-nums">
                {page + 1} / {pages}
              </span>
              <Button
                variant="subtle"
                size="sm"
                disabled={page === pages - 1}
                onClick={() => setPage(page + 1)}
                aria-label={t('ocr.next')}
              >
                →
              </Button>
            </div>
          )}
        </div>
      </div>

      <Dialog
        open={cropModalOpen}
        onClose={() => setCropModalOpen(false)}
        size="lg"
        title={t('ocr.crop_modal_title', { defaultValue: 'Select Subtitle Region' })}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setCropModalOpen(false)}>
              {t('common.cancel', { defaultValue: 'Cancel' })}
            </Button>
            <Button
              variant="primary"
              disabled={!tempCrop}
              onClick={() => {
                setSavedCrop(tempCrop);
                setCropModalOpen(false);
                if (pendingReplaceRef.current) {
                  pendingReplaceRef.current(tempCrop);
                  pendingReplaceRef.current = null;
                }
              }}
            >
              {t('ocr.confirm_region', { defaultValue: 'Confirm Region' })}
            </Button>
          </div>
        }
      >
        <div className="space-y-3">
          <p className="text-sm text-fg-muted">
            {t('ocr.crop_hint', {
              defaultValue:
                'Draw a box over the subtitle area on the video. This region will be remembered for OCR replacements.',
            })}
          </p>
          <OcrRegionEditor videoUrl={videoUrl} rect={tempCrop} onChange={setTempCrop} />
        </div>
      </Dialog>
    </section>
  );
}
