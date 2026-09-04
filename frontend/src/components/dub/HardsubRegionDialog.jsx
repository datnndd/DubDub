import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Download, ScanText, X } from 'lucide-react';
import { Button } from '../../ui';
import { API } from '../../api/client';

/**
 * HardsubRegionDialog — vẽ vùng phụ đề trên preview video rồi quét OCR.
 *
 * Flow: tua video đến lúc phụ đề hiện rõ → kéo hình chữ nhật trên khung →
 * "Bắt đầu quét" gửi crop rect (0..1) xuống /dub/hardsub-extract. Kết quả:
 * transcript được thay + file hardsub.srt tải được từ job dir.
 *
 * Toạ độ chuẩn hoá theo KHUNG VIDEO HIỂN THỊ (video giữ tỉ lệ gốc, không
 * letterbox) — map 1:1 với pixel của video thật.
 */
export default function HardsubRegionDialog({
  open,
  onClose,
  jobId,
  running = false,
  result = null, // { ok: true, count } | { error } — từ useDubWorkflow
  onExtract,
}) {
  const { t } = useTranslation();
  const overlayRef = useRef(null);
  const [rect, setRect] = useState(null); // {left, top, right, bottom} 0..1
  const [drag, setDrag] = useState(null);

  useEffect(() => {
    if (open) {
      setRect(null);
      setDrag(null);
    }
  }, [open]);

  const clamp01 = (v) => Math.min(Math.max(v, 0), 1);

  const _pt = (e) => {
    const box = overlayRef.current.getBoundingClientRect();
    return {
      x: clamp01((e.clientX - box.left) / box.width),
      y: clamp01((e.clientY - box.top) / box.height),
    };
  };

  const onPointerDown = (e) => {
    if (running) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    const p = _pt(e);
    setDrag({ x0: p.x, y0: p.y, x1: p.x, y1: p.y });
    setRect(null);
  };
  const onPointerMove = (e) => {
    if (!drag) return;
    const p = _pt(e);
    setDrag({ ...drag, x1: p.x, y1: p.y });
  };
  const onPointerUp = () => {
    if (!drag) return;
    const left = Math.min(drag.x0, drag.x1);
    const right = Math.max(drag.x0, drag.x1);
    const top = Math.min(drag.y0, drag.y1);
    const bottom = Math.max(drag.y0, drag.y1);
    setDrag(null);
    if (right - left >= 0.03 && bottom - top >= 0.02) {
      setRect({ left, top, right, bottom });
    }
  };

  const usePreset = () => {
    setRect({ left: 0, top: 0.55, right: 1, bottom: 1 });
  };

  const start = () => {
    if (!onExtract || running || !rect) return;
    if (!window.confirm(t('dub.hardsub_confirm'))) return;
    Promise.resolve(onExtract({ mode: 'ocr', crop: rect })).catch(() => {});
  };

  if (!open) return null;

  const dragRect = drag
    ? {
        left: Math.min(drag.x0, drag.x1) * 100,
        top: Math.min(drag.y0, drag.y1) * 100,
        width: Math.abs(drag.x1 - drag.x0) * 100,
        height: Math.abs(drag.y1 - drag.y0) * 100,
      }
    : null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-[16px]">
      <div className="w-full max-w-[720px] max-h-[92vh] overflow-auto rounded-[var(--chrome-radius-pill)] [border:1px_solid_var(--chrome-border)] bg-[var(--chrome-bg)] p-[16px]">
        <div className="flex items-center justify-between gap-[8px] mb-[8px]">
          <h3 className="font-[family-name:var(--chrome-font-mono)] text-[length:var(--chrome-label-size)] tracking-[var(--chrome-label-track)] uppercase text-[var(--chrome-fg)] font-semibold">
            {t('dub.hardsub_dialog_title')}
          </h3>
          <Button variant="ghost" size="sm" onClick={onClose} title={t('terms_review.close_title')}>
            <X size={12} />
          </Button>
        </div>

        <div className="relative select-none">
          <video
            src={jobId ? `${API}/dub/media/${jobId}` : undefined}
            controls
            muted
            playsInline
            preload="metadata"
            className="w-full block bg-black"
          />
          {/* Overlay vẽ vùng — phủ đúng khung video (video không letterbox) */}
          <div
            ref={overlayRef}
            className="absolute inset-0 cursor-crosshair"
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
          >
            {dragRect && (
              <div
                className="absolute [border:2px_solid_#fabe2b] bg-[rgba(250,190,43,0.12)] pointer-events-none"
                style={{
                  left: `${dragRect.left}%`,
                  top: `${dragRect.top}%`,
                  width: `${dragRect.width}%`,
                  height: `${dragRect.height}%`,
                }}
              />
            )}
          </div>
        </div>

        <p className="text-[length:var(--text-xs)] text-[var(--chrome-fg-muted)] leading-[1.5] mt-[8px]">
          {t('dub.hardsub_pick_hint')}
        </p>

        {result?.error && (
          <p className="text-[length:var(--text-xs)] text-[#fb4934] mt-[8px] break-words">
            {result.error}
          </p>
        )}
        {result?.ok && (
          <div className="mt-[8px] p-[8px] rounded-[var(--chrome-radius-pill)] [border:1px_solid_var(--chrome-border)] bg-[var(--chrome-hover-bg)]">
            <p className="text-[length:var(--text-xs)] text-[var(--chrome-fg)] mb-[6px]">
              {t('dub.hardsub_result_done', { count: result.count })}
            </p>
            <a
              href={`${API}/dub/hardsub-srt/${jobId}`}
              download="hardsub.srt"
              className="inline-flex items-center gap-[5px] text-[length:var(--text-xs)] text-[var(--chrome-accent)] underline cursor-pointer"
            >
              <Download size={11} /> {t('dub.hardsub_download')}
            </a>
          </div>
        )}

        <div className="flex items-center gap-[8px] flex-wrap mt-[12px]">
          <Button
            variant="primary"
            size="sm"
            onClick={start}
            disabled={!rect || running}
            loading={running}
            leading={!running && <ScanText size={11} />}
          >
            {t('dub.hardsub_start')}
          </Button>
          <Button
            variant="subtle"
            size="sm"
            onClick={usePreset}
            disabled={running}
            title={t('dub.hardsub_band_preset')}
          >
            {t('dub.hardsub_band_preset')}
          </Button>
          {running && (
            <span className="text-[length:var(--text-xs)] text-[var(--chrome-fg-muted)]">
              {t('dub.hardsub_running_hint')}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
