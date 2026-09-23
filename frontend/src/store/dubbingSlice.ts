import { StateCreator } from 'zustand';
import type { Speaker, VoiceOption, DubbingTuning } from '../types/dubbing';
import type { Segment } from '../types/segment';
import { fetchVoices } from '../api/settings';
import {
  type CustomVoice,
  type CreateVoicePayload,
  fetchCustomVoices,
  createCustomVoice as apiCreateCustomVoice,
  updateCustomVoice as apiUpdateCustomVoice,
  deleteCustomVoice as apiDeleteCustomVoice,
} from '../api/voices';

const SPEAKER_COLORS = ['amber', 'secondary', 'emerald', 'sky', 'indigo', 'purple', 'rose'];

export interface DubbingSlice {
  speakers: Speaker[];
  speakerVoiceMap: Record<string, string>;
  segmentVoiceOverrides: Record<number, string>;
  tuning: DubbingTuning;
  voices: VoiceOption[];
  customVoices: CustomVoice[];
  activePreviewVoiceId: string | null;
  isCreateVoiceModalOpen: boolean;
  isVoiceManagerDrawerOpen: boolean;

  loadVoices: () => Promise<void>;
  loadCustomVoices: (provider?: number) => Promise<void>;
  createVoice: (payload: CreateVoicePayload) => Promise<CustomVoice>;
  updateVoice: (id: string, updates: Partial<CustomVoice>) => Promise<void>;
  deleteVoice: (id: string, hard?: boolean) => Promise<void>;
  setCreateVoiceModalOpen: (open: boolean) => void;
  setVoiceManagerDrawerOpen: (open: boolean) => void;
  setActivePreviewVoiceId: (id: string | null) => void;

  setSpeakerVoice: (speakerId: string, voiceId: string) => void;
  setSegmentVoiceOverride: (segmentId: number, voiceId: string) => void;
  clearSegmentVoiceOverride: (segmentId: number) => void;
  updateTuning: (key: keyof DubbingTuning, value: any) => void;
  getDistinctSpeakers: () => Speaker[];
  getResolvedVoiceForSegment: (segment: Segment) => string;
}

export const createDubbingSlice: StateCreator<any, [], [], DubbingSlice> = (set, get) => ({
  speakers: [
    {
      id: "spk_1",
      code: "AC",
      name: "Alex Carter",
      role: "Keynote Speaker",
      preset: "Studio Warmth v4.2",
      clarity: "98%",
      coverage: "86%",
      color: "amber",
    },
    {
      id: "spk_2",
      code: "ER",
      name: "Elena Rostova",
      role: "Guest / Interviewer",
      preset: "Crisp Broadcast",
      clarity: "99%",
      coverage: "14%",
      color: "secondary",
    },
  ],
  speakerVoiceMap: Object.create(null),
  segmentVoiceOverrides: {},
  tuning: {
    pace: 1.0,
    timbreWarmth: 62,
    ducking: "85/15",
  },
  voices: [],
  customVoices: [],
  activePreviewVoiceId: null,
  isCreateVoiceModalOpen: false,
  isVoiceManagerDrawerOpen: false,

  loadVoices: async () => {
    try {
      const ttsType = get().backend?.config?.ttsType ?? 2;
      const [vList, cList] = await Promise.all([
        fetchVoices(ttsType),
        fetchCustomVoices(ttsType).catch(() => []),
      ]);

      const normalizedVoices: VoiceOption[] = (vList || []).map((item: any) => {
        if (typeof item === 'string') {
          return {
            id: item,
            name: item,
            provider: ttsType,
            kind: item.toLowerCase() === 'clone' ? 'clone' : (item === 'No' ? 'preset' : 'preset'),
          };
        }
        return {
          id: item.id || item.name,
          name: item.name || item.id,
          provider: item.provider ?? ttsType,
          kind: item.kind ?? 'preset',
          sampleUrl: item.sampleUrl,
        };
      });

      set({ voices: normalizedVoices, customVoices: cList || [] });
    } catch (err) {
      console.warn('Failed to load voices:', err);
    }
  },

  loadCustomVoices: async (provider?: number) => {
    try {
      const p = provider ?? get().backend?.config?.ttsType ?? 2;
      const cList = await fetchCustomVoices(p);
      set({ customVoices: cList || [] });
    } catch (err) {
      console.warn('Failed to load custom voices:', err);
    }
  },

  createVoice: async (payload: CreateVoicePayload) => {
    const newVoice = await apiCreateCustomVoice(payload);
    await get().loadVoices();
    return newVoice;
  },

  updateVoice: async (id: string, updates: Partial<CustomVoice>) => {
    await apiUpdateCustomVoice(id, updates);
    await get().loadVoices();
  },

  deleteVoice: async (id: string, hard: boolean = false) => {
    await apiDeleteCustomVoice(id, hard);
    await get().loadVoices();
  },

  setCreateVoiceModalOpen: (open: boolean) => set({ isCreateVoiceModalOpen: open }),
  setVoiceManagerDrawerOpen: (open: boolean) => set({ isVoiceManagerDrawerOpen: open }),
  setActivePreviewVoiceId: (id: string | null) => set({ activePreviewVoiceId: id }),

  setSpeakerVoice: (speakerId: string, voiceId: string) => {
    if (!speakerId || speakerId === '__proto__' || speakerId === 'constructor' || speakerId === 'prototype') return;
    set((state: any) => {
      const map = { ...(state.speakerVoiceMap || {}) };
      map[speakerId] = voiceId;
      return { speakerVoiceMap: map };
    });
    get().triggerAutosave();
  },

  setSegmentVoiceOverride: (segmentId: number, voiceId: string) => {
    if (isNaN(segmentId)) return;
    set((state: any) => {
      const overrides = { ...(state.segmentVoiceOverrides || {}) };
      if (!voiceId) {
        delete overrides[segmentId];
      } else {
        overrides[segmentId] = voiceId;
      }
      return { segmentVoiceOverrides: overrides };
    });
    get().triggerAutosave();
  },

  clearSegmentVoiceOverride: (segmentId: number) => {
    set((state: any) => {
      const overrides = { ...(state.segmentVoiceOverrides || {}) };
      delete overrides[segmentId];
      return { segmentVoiceOverrides: overrides };
    });
    get().triggerAutosave();
  },

  updateTuning: (key: keyof DubbingTuning, value: any) => {
    set((state: any) => ({
      tuning: {
        ...state.tuning,
        [key]: value,
      },
    }));
    get().triggerAutosave();
  },

  getDistinctSpeakers: (): Speaker[] => {
    const segments: Segment[] = get().segments || [];
    if (!segments || segments.length === 0) {
      return get().speakers || [];
    }

    const seen = new Map<string, Speaker>();
    let colorIdx = 0;

    for (const seg of segments) {
      const spkId = String(seg.speakerId || seg.speakerName || seg.speakerLabel || 'Speaker 1').trim();
      if (!spkId) continue;
      if (!seen.has(spkId)) {
        const words = spkId.split(/[\s_]+/);
        const code = words.length > 1
          ? `${words[0][0]}${words[1][0]}`.toUpperCase()
          : spkId.slice(0, 2).toUpperCase();
        seen.set(spkId, {
          id: spkId,
          code,
          name: seg.speakerName || spkId,
          role: 'Speaker',
          color: SPEAKER_COLORS[colorIdx % SPEAKER_COLORS.length],
        });
        colorIdx++;
      }
    }

    return Array.from(seen.values());
  },

  getResolvedVoiceForSegment: (segment: Segment): string => {
    if (!segment) return 'default';
    const overrides = get().segmentVoiceOverrides || {};
    if (overrides[segment.id]) return overrides[segment.id];
    const map = get().speakerVoiceMap || {};
    if (segment.speakerId && map[segment.speakerId]) return map[segment.speakerId];
    const voices = get().voices || [];
    return voices[0]?.id || 'default';
  },
});
