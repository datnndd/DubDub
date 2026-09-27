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
  transcriptOptions: {
    utterances?: Segment[];
    paragraphs?: Segment[];
  } | null;
  selectedSegmentOption: 'utterances' | 'paragraphs';
  showSegmentationModal: boolean;

  setSegments: (segments: Segment[]) => void;
  setTranscriptOptions: (options: { utterances?: Segment[]; paragraphs?: Segment[] } | null) => void;
  selectSegmentationOption: (option: 'utterances' | 'paragraphs') => void;
  setShowSegmentationModal: (show: boolean) => void;
  setActiveSegmentId: (id: number) => void;
  setSearchQuery: (query: string) => void;
  updateSegmentText: (id: number, text: string, isTarget?: boolean) => void;
  updateSegmentTiming: (id: number, startSec: number, endSec: number) => void;
  splitSegment: (id: number, splitTime?: number) => void;
  deleteSegment: (id: number) => void;
  mergeWithNextSegment: (id: number) => void;
  extractOcrForSegment: (segmentId: number) => Promise<void>;
  runBatchTranslation: (sourceLang?: string, targetLang?: string) => Promise<void>;
  translateSingleSegment: (segmentId: number) => Promise<void>;
  closeTranslationModal: () => void;
}

export function buildTranslationRequest(state: any) {
  return {
    segments: state.segments,
    sourceLanguage: state.languages?.source?.code || 'zh-cn',
    targetLanguage: state.languages?.target?.code || 'vi',
    translateType: state.backend?.config?.translateType ?? 0,
    translationMode: state.backend?.config?.translationMode || 'srt',
  };
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
  transcriptOptions: null,
  selectedSegmentOption: 'utterances',
  showSegmentationModal: false,

  setSegments: (segments: Segment[]) => {
    set({ segments });
    get().triggerAutosave();
  },

  setTranscriptOptions: (options) => {
    if (!options) {
      set({ transcriptOptions: null, showSegmentationModal: false });
      return;
    }
    const hasBoth = Boolean(options.utterances?.length && options.paragraphs?.length);
    const curSelected = get().selectedSegmentOption || 'utterances';
    const chosen = curSelected === 'paragraphs' && options.paragraphs?.length
      ? options.paragraphs
      : (options.utterances?.length ? options.utterances : options.paragraphs || []);

    set({
      transcriptOptions: options,
      showSegmentationModal: hasBoth,
      ...(chosen.length > 0 && get().segments.length === 0 ? { segments: chosen, activeSegmentId: chosen[0]?.id || 1 } : {}),
    });
    get().triggerAutosave();
  },

  selectSegmentationOption: (option) => {
    const opts = get().transcriptOptions;
    if (!opts) return;
    const chosen = option === 'paragraphs' ? opts.paragraphs : opts.utterances;
    if (Array.isArray(chosen) && chosen.length > 0) {
      set({
        selectedSegmentOption: option,
        segments: chosen,
        activeSegmentId: chosen[0]?.id || 1,
        showSegmentationModal: false,
      });
      get().triggerAutosave();
    }
  },

  setShowSegmentationModal: (show: boolean) => set({ showSegmentationModal: show }),

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
          return { ...s, sourceText: text, text, cps, cpsStatus };
        }
      });
      const nextOptions = state.transcriptOptions ? {
        ...state.transcriptOptions,
        [state.selectedSegmentOption]: next,
      } : state.transcriptOptions;
      return {
        segments: next,
        transcriptOptions: nextOptions,
        dubbingStatus: isTarget && state.dubbingStatus === 'completed' ? 'idle' : state.dubbingStatus,
      };
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
      const nextOptions = state.transcriptOptions ? {
        ...state.transcriptOptions,
        [state.selectedSegmentOption]: next,
      } : state.transcriptOptions;
      return { segments: next, transcriptOptions: nextOptions };
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

  runBatchTranslation: async (sourceLang?: string, targetLang?: string) => {
    if (sourceLang && get().languages?.source?.code !== sourceLang) {
      const avail = get().backend?.options?.languages || [];
      const opt = avail.find((l: any) => l.code === sourceLang);
      get().updateSourceLanguage(sourceLang, opt?.name || sourceLang);
    }
    if (targetLang && get().languages?.target?.code !== targetLang) {
      const avail = get().backend?.options?.languages || [];
      const opt = avail.find((l: any) => l.code === targetLang);
      get().updateTargetLanguage(targetLang, opt?.name || targetLang);
    }

    const curSource = sourceLang || get().languages?.source?.code || 'zh-cn';
    const curTarget = targetLang || get().languages?.target?.code || 'vi';

    set({
      translationModal: {
        active: true,
        status: 'translating',
        progress: 25,
        message: `Translating transcript from ${curSource} to ${curTarget}…`,
        error: null,
      },
    });

    try {
      const req: any = buildTranslationRequest(get());
      if (sourceLang) req.sourceLanguage = sourceLang;
      if (targetLang) req.targetLanguage = targetLang;
      if (get().activeProjectId) req.projectId = get().activeProjectId;
      if (get().backend?.mediaId) req.mediaId = get().backend.mediaId;
      const resp = await requestTranslate(req);

      if (resp.ok && resp.segments) {
        const segMap = new Map<number, string>();
        resp.segments.forEach((s: any, idx: number) => {
          let trans = '';
          if (typeof s.targetText === 'string' && s.targetText.trim()) {
            trans = s.targetText;
          } else if (typeof s.text === 'string' && s.text.trim()) {
            if (!s.sourceText || s.text !== s.sourceText) {
              trans = s.text;
            }
          }
          if (!trans && (s.targetText || s.text)) {
            trans = s.targetText || s.text;
          }

          if (s.id !== undefined && s.id !== null) {
            segMap.set(Number(s.id), trans);
          }
          if (s.line !== undefined && s.line !== null) {
            segMap.set(Number(s.line), trans);
          }
          segMap.set(idx + 1, trans);
          segMap.set(idx, trans);
        });

        const nextSegments = get().segments.map((s: Segment, index: number) => {
          const respSeg = resp.segments[index];
          let translated = '';
          if (respSeg && typeof respSeg.targetText === 'string' && respSeg.targetText.trim()) {
            translated = respSeg.targetText;
          } else if (respSeg && typeof respSeg.text === 'string' && respSeg.text.trim() && (!respSeg.sourceText || respSeg.text !== respSeg.sourceText)) {
            translated = respSeg.text;
          } else {
            translated = segMap.get(Number(s.id)) ?? segMap.get(index + 1) ?? s.targetText ?? '';
          }

          const dur = Math.max(0.1, (s.endSec || 0) - (s.startSec || 0));
          const cps = Number(((translated || '').trim().length / dur).toFixed(1));
          const cpsStatus = cps <= 14.5 ? 'Optimal' : cps <= 18.0 ? 'Good' : 'Warning';

          return {
            ...s,
            targetText: translated,
            cps,
            cpsStatus,
          };
        });

        const curOptions = get().transcriptOptions;
        const curOptionKey = get().selectedSegmentOption;
        const nextOptions = curOptions ? {
          ...curOptions,
          [curOptionKey]: nextSegments,
        } : curOptions;

        set({
          segments: nextSegments,
          transcriptOptions: nextOptions,
          translationModal: {
            active: true,
            status: 'completed',
            progress: 100,
            message: 'Translation completed successfully',
            error: null,
          },
        });
        get().triggerAutosave();

        setTimeout(() => {
          if (get().translationModal.status === 'completed') {
            get().closeTranslationModal();
          }
        }, 1200);
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

  translateSingleSegment: async (segmentId: number) => {
    const seg = get().segments.find((s: Segment) => s.id === segmentId);
    if (!seg) return;
    const text = seg.sourceText || seg.text || '';
    if (!text.trim()) return;

    try {
      const curSource = get().languages?.source?.code || 'zh-cn';
      const curTarget = get().languages?.target?.code || 'vi';
      const req: any = {
        segments: [{ ...seg, text, sourceText: text }],
        sourceLanguage: curSource,
        targetLanguage: curTarget,
        translateType: get().backend?.config?.translateType ?? 0,
        translationMode: get().backend?.config?.translationMode || 'srt',
      };
      if (get().activeProjectId) {
        req.projectId = get().activeProjectId;
      }
      const resp = await requestTranslate(req);
      if (resp.ok && resp.segments && resp.segments.length > 0) {
        const item = resp.segments[0];
        const trans = (item.targetText && item.targetText.trim())
          ? item.targetText
          : (item.text && (!item.sourceText || item.text !== item.sourceText))
            ? item.text
            : (item.targetText || item.text || '');
        if (trans) {
          get().updateSegmentText(segmentId, trans, true);
        }
      }
    } catch (err) {
      console.warn('Single segment translation failed:', err);
    }
  },

  closeTranslationModal: () => {
    set((state: any) => ({
      translationModal: { ...state.translationModal, active: false },
    }));
  },
});
