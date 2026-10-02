import React, { useRef, useState } from 'react';
import type { Segment } from '../types/segment';

type Roi = [number, number, number, number];

export function roiFromDrag(start: [number, number], end: [number, number]): Roi {
  const clamp = (value: number) => Math.max(0, Math.min(1, value));
  const x1 = clamp(Math.min(start[0], end[0]));
  const y1 = clamp(Math.min(start[1], end[1]));
  const x2 = clamp(Math.max(start[0], end[0]));
  const y2 = clamp(Math.max(start[1], end[1]));
  return [x1, y1, x2 - x1, y2 - y1];
}

export interface BatchOcrResult {
  segment: Segment;
  text?: string;
  confidence?: number;
  error?: string;
  applied?: boolean;
}

interface Props {
  segment: Segment;
  batchSegments?: Segment[];
  batchResults?: BatchOcrResult[];
  currentSegments?: Segment[];
  progress?: number;
  videoUrl: string;
  roi: Roi;
  onRoiChange: (roi: Roi) => void;
  onExtract: () => void;
  onClose: () => void;
  loading: boolean;
  result: { text: string; confidence?: number; applied?: boolean } | null;
  error: string | null;
}

export const Stage2OcrDialog: React.FC<Props> = ({
  segment, batchSegments, batchResults = [], currentSegments = [], progress = 0,
  videoUrl, roi, onRoiChange, onExtract, onClose, loading, result, error,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const dragStart = useRef<[number, number] | null>(null);
  const [dragRoi, setDragRoi] = useState<Roi | null>(null);
  const [previewError, setPreviewError] = useState(false);
  const isBatch = (batchSegments?.length || 0) > 1;
  const isCurrent = (entry: BatchOcrResult) => currentSegments.some((current) =>
    current.id === entry.segment.id && current.startSec === entry.segment.startSec && current.endSec === entry.segment.endSec);
  const visibleRoi = dragRoi ?? roi;

  const point = (event: React.PointerEvent<HTMLDivElement>): [number, number] => {
    const bounds = videoRef.current!.getBoundingClientRect();
    return [(event.clientX - bounds.left) / bounds.width, (event.clientY - bounds.top) / bounds.height];
  };

  const changeCoordinate = (index: number, percent: number) => {
    if (!Number.isFinite(percent)) return;
    const next = [...roi] as Roi;
    next[index] = Math.max(0, Math.min(1, percent / 100));
    if (next[0] + next[2] > 1) next[index === 0 ? 2 : 0] = 1 - next[index === 0 ? 0 : 2];
    if (next[1] + next[3] > 1) next[index === 1 ? 3 : 1] = 1 - next[index === 1 ? 1 : 3];
    onRoiChange(next);
  };

  return (
    <div role="dialog" aria-modal="true" aria-label="Extract text from video" data-testid="stage2-ocr-dialog"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl bg-white p-5 shadow-2xl space-y-3">
        <div className="flex justify-between gap-3">
          <div>
            <h2 className="font-bold text-stone-900">{isBatch ? `OCR Extract · ${batchSegments?.length} selected segments` : `OCR Extract · Segment ${segment.id}`}</h2>
            <p className="text-xs text-stone-600">Select the subtitle region, then run OCR. Recognized text replaces each matching source subtitle automatically.</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close OCR dialog" className="text-stone-600 hover:text-stone-900">✕</button>
        </div>
        {videoUrl ? (
          <div className="flex justify-center bg-black rounded-lg overflow-hidden">
            <div className="relative inline-block touch-none select-none"
              onPointerDown={(event) => {
                if (!videoRef.current) return;
                dragStart.current = point(event);
                event.currentTarget.setPointerCapture(event.pointerId);
              }}
              onPointerMove={(event) => {
                if (!dragStart.current || !videoRef.current) return;
                const next = roiFromDrag(dragStart.current, point(event));
                if (next[2] > 0.01 && next[3] > 0.01) setDragRoi(next);
              }}
              onPointerUp={(event) => {
                if (dragStart.current && videoRef.current) {
                  const next = roiFromDrag(dragStart.current, point(event));
                  if (next[2] > 0.01 && next[3] > 0.01) onRoiChange(next);
                }
                dragStart.current = null;
                setDragRoi(null);
              }}
              onPointerCancel={() => { dragStart.current = null; setDragRoi(null); }}
            >
              <video ref={videoRef} src={videoUrl} className="block max-w-full max-h-[45vh]"
                muted playsInline preload="auto"
                onLoadedMetadata={(event) => { event.currentTarget.currentTime = (segment.startSec + segment.endSec) / 2; }}
                onError={() => setPreviewError(true)}
              />
              <div data-testid="ocr-roi-overlay" className="absolute border-2 border-amber-400 bg-amber-300/20 pointer-events-none"
                style={{ left: `${visibleRoi[0] * 100}%`, top: `${visibleRoi[1] * 100}%`, width: `${visibleRoi[2] * 100}%`, height: `${visibleRoi[3] * 100}%` }} />
            </div>
          </div>
        ) : <p role="alert" className="text-sm text-rose-700">No video preview is available for OCR.</p>}
        {previewError && <p role="alert" className="text-xs text-rose-700">The video frame could not be displayed. Check that the uploaded video is still available.</p>}
        <div className="grid grid-cols-4 gap-2">
          {(['Left', 'Top', 'Width', 'Height'] as const).map((label, index) => (
            <label key={label} className="text-xs text-stone-700">{label} %
              <input type="number" min="0" max="100" step="1" aria-label={`${label} percent`}
                value={Math.round(roi[index] * 100)} onChange={(event) => changeCoordinate(index, Number(event.target.value))}
                className="w-full rounded border border-stone-300 p-1" />
            </label>
          ))}
        </div>
        <button type="button" onClick={onExtract} disabled={loading || !videoUrl || roi[2] <= 0 || roi[3] <= 0}
          className="rounded bg-[#8D4B00] px-3 py-1.5 text-xs font-bold text-white disabled:opacity-50">
          {loading ? `Reading video frames…${isBatch ? ` ${progress}/${batchSegments?.length}` : ''}` : isBatch ? 'Extract Selected Text' : 'Extract Text'}
        </button>
        {error && <p role="alert" className="text-xs text-rose-700">{error}</p>}
        {isBatch && batchResults.length > 0 && (
          <div className="space-y-3 border-t border-stone-200 pt-3" data-testid="ocr-batch-results">
            {batchResults.map((entry) => {
              const current = isCurrent(entry);
              return <div key={entry.segment.id} data-testid={`ocr-result-${entry.segment.id}`} className="rounded border border-stone-200 p-2 space-y-1">
                <p className="text-xs font-semibold text-stone-700">Segment {entry.segment.id} · {entry.segment.startSec.toFixed(2)}s–{entry.segment.endSec.toFixed(2)}s
                  {entry.confidence != null && !entry.error ? ` · ${Math.round(entry.confidence * 100)}% confidence` : ''}</p>
                {!current && <p role="alert" className="text-xs text-amber-800">This segment or its timing changed. Run OCR again for this segment.</p>}
                {entry.error && <p role="alert" className="text-xs text-rose-700">{entry.error}</p>}
                {entry.text ? <><p className="text-sm text-stone-800 whitespace-pre-wrap">{entry.text}</p>
                  {!entry.error && <p className="text-xs text-emerald-700">{entry.applied ? 'Source subtitle updated and saved.' : 'Source subtitle unchanged.'}</p>}</>
                  : !entry.error && <p className="text-xs text-stone-600">No text was found in this time range.</p>}
              </div>;
            })}
          </div>
        )}
        {!isBatch && result && (
          <div className="space-y-2 border-t border-stone-200 pt-3">
            <p className="text-xs text-stone-600">Recognized text{result.confidence != null ? ` · ${Math.round(result.confidence * 100)}% confidence` : ''}</p>
            {result.text ? (
              <>
                <p className="text-sm text-stone-800 whitespace-pre-wrap">{result.text}</p>
                {!error && <p className="text-xs text-emerald-700">{result.applied ? 'Source subtitle updated and saved.' : 'Source subtitle unchanged.'}</p>}
              </>
            ) : <p className="text-xs text-stone-600">No text was found in this region. Adjust the crop and try again.</p>}
          </div>
        )}
      </div>
    </div>
  );
};
