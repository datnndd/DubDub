import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Play, Pause } from 'lucide-react';
import { Button } from '../../ui';
import { cn } from '../../lib/utils';
import { dragOcrRegion, editOcrCoordinate, formatOcrTime } from '../../utils/ocrRegion';

const corners = { nw: 'left-0 top-0 cursor-nwse-resize', ne: 'right-0 top-0 cursor-nesw-resize',
  sw: 'left-0 bottom-0 cursor-nesw-resize', se: 'right-0 bottom-0 cursor-nwse-resize' };

export default function OcrRegionEditor({ videoUrl, rect, onChange, disabled = false }) {
  const { t } = useTranslation();
  const videoRef = useRef(null), overlayRef = useRef(null), dragRef = useRef(null);
  const [aspect, setAspect] = useState(16 / 9);
  const [duration, setDuration] = useState(0), [position, setPosition] = useState(0);
  const [playing, setPlaying] = useState(false);
  const point = (event) => {
    const box = overlayRef.current.getBoundingClientRect();
    return { x: Math.max(0, Math.min(1, (event.clientX - box.left) / box.width)),
      y: Math.max(0, Math.min(1, (event.clientY - box.top) / box.height)) };
  };
  const pointerDown = (event) => {
    if (disabled || event.button > 0) return;
    videoRef.current?.pause();
    event.currentTarget.setPointerCapture(event.pointerId);
    const start = point(event);
    const inside = rect && start.x >= rect.left && start.x <= rect.right && start.y >= rect.top && start.y <= rect.bottom;
    dragRef.current = { start, rect, action: event.target.dataset.resize || (inside ? 'move' : 'draw') };
  };
  const pointerMove = (event) => {
    const drag = dragRef.current;
    if (!drag || disabled) return;
    onChange(dragOcrRegion(drag.rect, drag.start, point(event), drag.action));
  };
  const pointerUp = (event) => {
    pointerMove(event);
    dragRef.current = null;
  };
  return (
    <div className="min-w-0 space-y-3">
      <div className="relative mx-auto w-full overflow-hidden rounded-md bg-black"
        style={{ aspectRatio: aspect, maxWidth: `${48 * aspect}vh` }}>
        <video ref={videoRef} src={videoUrl} muted playsInline preload="metadata"
          className="block size-full object-contain" data-testid="ocr-region-video"
          onLoadedMetadata={() => {
            const video = videoRef.current;
            setDuration(Number.isFinite(video.duration) ? video.duration : 0);
            if (video.videoWidth && video.videoHeight) setAspect(video.videoWidth / video.videoHeight);
          }} onTimeUpdate={() => setPosition(videoRef.current.currentTime)}
          onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} />
        <div ref={overlayRef} data-testid="ocr-region-overlay"
          className={cn('absolute inset-0 touch-none select-none', disabled ? 'cursor-default' : 'cursor-crosshair')}
          onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp}
          onPointerCancel={() => { dragRef.current = null; }}>
          {rect && <div data-testid="ocr-selection"
            className="absolute border-2 border-[var(--color-brand)] bg-[var(--color-brand)]/10 cursor-move"
            style={{ left: `${rect.left * 100}%`, top: `${rect.top * 100}%`,
              width: `${(rect.right - rect.left) * 100}%`, height: `${(rect.bottom - rect.top) * 100}%` }}>
            {!disabled && Object.entries(corners).map(([corner, classes]) =>
              <span key={corner} data-resize={corner} data-testid={`ocr-resize-${corner}`}
                className={cn('absolute size-4 border-2 border-white bg-[var(--color-brand)]', classes)} />)}
          </div>}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" aria-label={t(playing ? 'player.pause' : 'player.play')}
          onClick={() => playing ? videoRef.current.pause() : videoRef.current.play().catch(() => {})}>
          {playing ? <Pause size={16} /> : <Play size={16} />}
        </Button>
        <input aria-label={t('player.seek')} type="range" min="0" max={duration || 1} step="0.1" value={position}
          className="min-w-0 flex-1 accent-[var(--color-brand)]"
          onChange={(e) => { videoRef.current.currentTime = Number(e.target.value); setPosition(Number(e.target.value)); }} />
        <span className="text-xs tabular-nums text-fg-muted">{formatOcrTime(position)} / {formatOcrTime(duration)}</span>
      </div>
      <p className="text-sm text-fg-muted text-pretty">{t('ocr.region_hint')}</p>
      {rect && <fieldset disabled={disabled} className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <legend className="sr-only">{t('ocr.adjust_region')}</legend>
        {['left', 'top', 'right', 'bottom'].map((edge) => <label key={edge} className="text-xs text-fg-muted">
          {t(`ocr.${edge}`)} (%)
          <input type="number" min="0" max="100" step="0.1"
            value={Math.round(rect[edge] * 1000) / 10}
            className="mt-1 w-full rounded-md border border-border bg-background p-2 text-fg tabular-nums"
            onChange={(e) => onChange(editOcrCoordinate(rect, edge, e.target.valueAsNumber))} />
        </label>)}
      </fieldset>}
      <div className="flex flex-wrap gap-2">
        <Button variant="subtle" size="sm" disabled={disabled}
          onClick={() => onChange({ left: 0.02, top: 0.65, right: 0.98, bottom: 0.98 })}>{t('dub.hardsub_band_preset')}</Button>
        <Button variant="subtle" size="sm" disabled={disabled}
          onClick={() => onChange({ left: 0, top: 0, right: 1, bottom: 1 })}>{t('dub.hardsub_full_frame')}</Button>
        {rect && <Button variant="ghost" size="sm" disabled={disabled} onClick={() => onChange(null)}>{t('dub.clear_selection')}</Button>}
      </div>
    </div>
  );
}
