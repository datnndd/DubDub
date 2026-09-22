import { StateCreator } from 'zustand';
import type { AudioMixSettings, SubtitleStyleSettings, EditVideoState } from '../types/editor';
import { uploadEditAsset } from '../api/media';
import { requestRender } from '../api/stages';

const DEFAULT_AUDIO_MIX: AudioMixSettings = { original: 0, dubbed: 100, background: 35 };

export interface EditVideoSlice {
  subtitleStyles: SubtitleStyleSettings;
  editVideo: EditVideoState;
  muteCache: Record<string, number>;

  setAudioMix: (channel: 'original' | 'dubbed' | 'background', val: any) => void;
  toggleAudioMute: (channel: 'original' | 'dubbed' | 'background') => void;
  setBackgroundAudio: (file: File | null) => Promise<void>;
  removeBackgroundAudio: () => void;
  setThumbnail: (file: File | null) => Promise<void>;
  removeThumbnail: () => void;
  updateSubtitleStyle: (key: keyof SubtitleStyleSettings, val: any) => void;
  setActiveInspectorTab: (tab: 'audio' | 'subtitles' | 'assets') => void;
  exportEditedVideo: () => Promise<void>;
}

export const createEditVideoSlice: StateCreator<any, [], [], EditVideoSlice> = (set, get) => ({
  subtitleStyles: {
    preset: 'clean',
    fontFamily: 'Arial',
    fontSize: 22,
    color: '#FFFFFF',
    outlineColor: '#000000',
    outlineWidth: 2,
    shadowColor: 'rgba(0,0,0,.75)',
    shadowSize: 2,
    aiLipSync: true,
    deReverb: true,
    faceRetouch: false,
    superRes4K: true,
  },
  editVideo: {
    audioMix: { ...DEFAULT_AUDIO_MIX },
    backgroundAudio: null,
    thumbnail: null,
    exporting: false,
    error: null,
    activeTab: 'audio',
  },
  muteCache: {},

  setAudioMix: (channel: 'original' | 'dubbed' | 'background', val: any) => {
    if (!['original', 'dubbed', 'background'].includes(channel)) return;
    const num = Number(val);
    const clamped = isNaN(num) ? 0 : Math.max(0, Math.min(150, num));
    set((state: any) => ({
      editVideo: {
        ...state.editVideo,
        audioMix: {
          ...state.editVideo.audioMix,
          [channel]: clamped,
        },
      },
    }));
    get().triggerAutosave();
  },

  toggleAudioMute: (channel: 'original' | 'dubbed' | 'background') => {
    if (!['original', 'dubbed', 'background'].includes(channel)) return;
    const curVal = get().editVideo.audioMix[channel];
    const cache = { ...(get().muteCache || {}) };

    if (curVal > 0) {
      cache[channel] = curVal;
      set((state: any) => ({
        muteCache: cache,
        editVideo: {
          ...state.editVideo,
          audioMix: {
            ...state.editVideo.audioMix,
            [channel]: 0,
          },
        },
      }));
    } else {
      const restored = cache[channel] && cache[channel] > 0
        ? cache[channel]
        : DEFAULT_AUDIO_MIX[channel] || 100;
      set((state: any) => ({
        editVideo: {
          ...state.editVideo,
          audioMix: {
            ...state.editVideo.audioMix,
            [channel]: restored,
          },
        },
      }));
    }
    get().triggerAutosave();
  },

  setBackgroundAudio: async (file: File | null) => {
    if (!file) return;
    try {
      const resp = await uploadEditAsset('background-audio', file);
      const url = URL.createObjectURL(file);
      set((state: any) => ({
        editVideo: {
          ...state.editVideo,
          backgroundAudio: { file, name: resp.name, url },
        },
      }));
      get().triggerAutosave();
    } catch (err: any) {
      console.warn('Failed to upload background audio:', err);
    }
  },

  removeBackgroundAudio: () => {
    const cur = get().editVideo.backgroundAudio;
    if (cur?.url && typeof URL !== 'undefined') {
      try { URL.revokeObjectURL(cur.url); } catch (_) {}
    }
    set((state: any) => ({
      editVideo: {
        ...state.editVideo,
        backgroundAudio: null,
      },
    }));
    get().triggerAutosave();
  },

  setThumbnail: async (file: File | null) => {
    if (!file) return;
    try {
      const resp = await uploadEditAsset('thumbnail', file);
      const url = URL.createObjectURL(file);
      set((state: any) => ({
        editVideo: {
          ...state.editVideo,
          thumbnail: { file, name: resp.name, url },
        },
      }));
      get().triggerAutosave();
    } catch (err: any) {
      console.warn('Failed to upload thumbnail:', err);
    }
  },

  removeThumbnail: () => {
    const cur = get().editVideo.thumbnail;
    if (cur?.url && typeof URL !== 'undefined') {
      try { URL.revokeObjectURL(cur.url); } catch (_) {}
    }
    set((state: any) => ({
      editVideo: {
        ...state.editVideo,
        thumbnail: null,
      },
    }));
    get().triggerAutosave();
  },

  updateSubtitleStyle: (key: keyof SubtitleStyleSettings, val: any) => {
    set((state: any) => ({
      subtitleStyles: {
        ...state.subtitleStyles,
        [key]: val,
      },
    }));
    get().triggerAutosave();
  },

  setActiveInspectorTab: (tab: 'audio' | 'subtitles' | 'assets') => {
    set((state: any) => ({
      editVideo: {
        ...state.editVideo,
        activeTab: tab,
      },
    }));
  },

  exportEditedVideo: async () => {
    const state = get();
    const mediaId = state.backend?.mediaId;
    if (!mediaId) return;

    set((s: any) => ({
      editVideo: { ...s.editVideo, exporting: true, error: null },
    }));

    try {
      const payload = {
        mediaId,
        projectId: state.activeProjectId,
        jobType: 'render',
        audioMix: state.editVideo.audioMix,
        subtitleStyles: state.subtitleStyles,
        segments: state.segments,
        speakerVoiceMap: state.speakerVoiceMap,
      };
      const res = await requestRender(payload);
      if (res.jobId) {
        state.subscribeToJob?.(res.jobId);
      }
    } catch (err: any) {
      set((s: any) => ({
        editVideo: { ...s.editVideo, exporting: false, error: err.message },
      }));
    }
  },
});
