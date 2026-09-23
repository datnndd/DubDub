import { StateCreator } from 'zustand';
import type { Segment } from '../types/segment';
import { formatTimecode } from './playbackSlice';
import { requestTranslate, requestOcrExtract } from '../api/stages';

const DEFAULT_SEGMENTS: Segment[] = [];

export interface TranscriptSlice {
  segments: Segment[];
  activeSegmentId: number;
  searchQuery: string;
  lockedTerms: Array<{ id: number; source: string; target: string }>;
  translationModal: {
    active: boolean;
    status: string;
    progress: number;
    message: string;
    error: string | null;
  };

  setSegments: (segments: Segment[]) => void;
  setActiveSegmentId: (id: number) => void;
  setSearchQuery: (query: string) => void;
  updateSegmentText: (id: number, text: string, isTarget?: boolean) => void;
  updateSegmentTiming: (id: number, startSec: number, endSec: number) => void;
  splitSegment: (id: number, splitTime?: number) => void;
  deleteSegment: (id: number) => void;
  mergeWithNextSegment: (id: number) => void;
  extractOcrForSegment: (segmentId: number) => Promise<void>;
  runBatchTranslation: () => Promise<void>;
  closeTranslationModal: () => void;
}

export const createTranscriptSlice: StateCreator<any, [], [], TranscriptSlice> = (set, get) => ({
  segments: DEFAULT_SEGMENTS,
  activeSegmentId: 1,
  searchQuery: '',
  lockedTerms: [
    { id: 1, source: "AI", target: "inteligencia artificial" },
    { id: 2, source: "vocoder", target: "vocoder" },
    { id: 3, source: "neural mesh", target: "malla neuronal" },
  ],
  translationModal: {
    active: false,
    status: 'idle',
    progress: 0,
    message: 'Translating transcript...',
    error: null,
  },

  setSegments: (segments: Segment[]) => {
    set({ segments });
    get().triggerAutosave();
  },

  setActiveSegmentId: (id: number) => set({ activeSegmentId: id }),

  setSearchQuery: (searchQuery: string) => set({ searchQuery }),

  updateSegmentText: (id: number, text: string, isTarget: boolean = false) => {
    set((state: any) => {
      const next = state.segments.map((s: Segment) => {
        if (s.id !== id) return s;
        const dur = Math.max(0.1, (s.endSec || 0) - (s.startSec || 0));
        const cps = Number((text.trim().length / dur).toFixed(1));
        const cpsStatus = cps <= 14.5 ? 'Optimal' : cps <= 18.0 ? 'Good' : 'Warning';
        if (isTarget) {
          return { ...s, targetText: text, cps, cpsStatus };
        } else {
          return { ...s, sourceText: text, cps, cpsStatus };
        }
      });
      return { segments: next };
    });
    get().triggerAutosave();
  },

  updateSegmentTiming: (id: number, startSec: number, endSec: number) => {
    if (isNaN(startSec) || isNaN(endSec) || startSec >= endSec) return;
    set((state: any) => {
      const next = state.segments.map((s: Segment) => {
        if (s.id !== id) return s;
        const dur = Math.max(0.1, endSec - startSec);
        const text = s.targetText || s.sourceText || '';
        const cps = Number((text.trim().length / dur).toFixed(1));
        const cpsStatus = cps <= 14.5 ? 'Optimal' : cps <= 18.0 ? 'Good' : 'Warning';
        return {
          ...s,
          startSec,
          endSec,
          startTime: formatTimecode(startSec),
          endTime: formatTimecode(endSec),
          cps,
          cpsStatus,
        };
      });
      return { segments: next };
    });
    get().triggerAutosave();
  },

  splitSegment: (id: number, splitTime?: number) => {
    set((state: any) => {
      const idx = state.segments.findIndex((s: Segment) => s.id === id);
      if (idx === -1) return state;
      const seg = state.segments[idx];
      const t = splitTime !== undefined ? splitTime : (seg.startSec + seg.endSec) / 2;
      const clamped = Math.max(seg.startSec + 0.1, Math.min(seg.endSec - 0.1, t));

      const newId = Math.max(0, ...state.segments.map((s: Segment) => s.id)) + 1;
      const words = (seg.sourceText || '').split(' ');
      const mid = Math.max(1, Math.floor(words.length / 2));
      const text1 = words.slice(0, mid).join(' ');
      const text2 = words.slice(mid).join(' ');

      const targetWords = (seg.targetText || '').split(' ');
      const targetMid = Math.max(1, Math.floor(targetWords.length / 2));
      const target1 = targetWords.slice(0, targetMid).join(' ');
      const target2 = targetWords.slice(targetMid).join(' ');

      const s1: Segment = {
        ...seg,
        endSec: clamped,
        endTime: formatTimecode(clamped),
        sourceText: text1,
        targetText: target1,
      };

      const s2: Segment = {
        ...seg,
        id: newId,
        startSec: clamped,
        startTime: formatTimecode(clamped),
        sourceText: text2,
        targetText: target2,
      };

      const next = [...state.segments];
      next.splice(idx, 1, s1, s2);
      return { segments: next };
    });
    get().triggerAutosave();
  },

  deleteSegment: (id: number) => {
    set((state: any) => ({
      segments: state.segments.filter((s: Segment) => s.id !== id),
    }));
    get().triggerAutosave();
  },

  mergeWithNextSegment: (id: number) => {
    set((state: any) => {
      const idx = state.segments.findIndex((s: Segment) => s.id === id);
      if (idx === -1 || idx === state.segments.length - 1) return state;
      const cur = state.segments[idx];
      const next = state.segments[idx + 1];

      const merged: Segment = {
        ...cur,
        endSec: next.endSec,
        endTime: next.endTime,
        sourceText: `${cur.sourceText} ${next.sourceText}`.trim(),
        targetText: `${cur.targetText} ${next.targetText}`.trim(),
      };

      const newSegs = [...state.segments];
      newSegs.splice(idx, 2, merged);
      return { segments: newSegs };
    });
    get().triggerAutosave();
  },

  extractOcrForSegment: async (segmentId: number) => {
    const mediaId = get().backend?.mediaId;
    if (!mediaId) return;
    const seg = get().segments.find((s: Segment) => s.id === segmentId);
    if (!seg) return;
    const roi = get().ocrCrop?.roi || [0.05, 0.75, 0.9, 0.2];

    try {
      const result = await requestOcrExtract({
        mediaId,
        roi,
        startSec: seg.startSec,
        endSec: seg.endSec,
        segmentId,
      });
      if (result.ok && result.text) {
        set((state: any) => ({
          segments: state.segments.map((s: Segment) =>
            s.id === segmentId
              ? { ...s, sourceText: result.text, hasOcrDiff: true, ocrSlideText: result.text }
              : s
          ),
        }));
        get().triggerAutosave();
      }
    } catch (err) {
      console.warn('OCR extraction failed:', err);
    }
  },

  runBatchTranslation: async () => {
    const segments = get().segments;
    const sourceLanguage = get().languages.source.code;
    const targetLanguage = get().languages.target.code;
    const translateType = get().backend.config.translateType;

    set({
      translationModal: {
        active: true,
        status: 'translating',
        progress: 25,
        message: 'Calling translation engine…',
        error: null,
      },
    });

    try {
      const resp = await requestTranslate({
        segments,
        sourceLanguage,
        targetLanguage,
        translateType,
      });

      if (resp.ok && resp.segments) {
        const segMap = new Map<number, string>();
        resp.segments.forEach((s: any) => {
          segMap.set(s.line || s.id, s.text || s.targetText);
        });

        set((state: any) => ({
          segments: state.segments.map((s: Segment, index: number) => {
            const translated = segMap.get(s.id) || segMap.get(index + 1);
            if (!translated) return s;
            return { ...s, targetText: translated };
          }),
          translationModal: {
            active: true,
            status: 'completed',
            progress: 100,
            message: 'Translation completed successfully',
            error: null,
          },
        }));
        get().triggerAutosave();
      }
    } catch (err: any) {
      set({
        translationModal: {
          active: true,
          status: 'failed',
          progress: 0,
          message: 'Translation failed',
          error: err.message,
        },
      });
    }
  },

  closeTranslationModal: () => {
    set((state: any) => ({
      translationModal: { ...state.translationModal, active: false },
    }));
  },
});
