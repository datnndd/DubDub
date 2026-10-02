import { StateCreator } from 'zustand';
import type { ProjectMetadata, BackendOptions } from '../types/project';
import type { OcrCropState } from '../types/segment';
import { uploadMedia } from '../api/media';
import { fetchOptions } from '../api/settings';
import { formatTimecode } from './playbackSlice';

export function formatBytes(bytes: number): string {
  if (!bytes || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

export interface DeepgramConfigOptions {
  utt_split?: number;
  diarize_model?: string;
  smart_format?: boolean;
  punctuate?: boolean;
  paragraphs?: boolean;
  utterances?: boolean;
  extra?: string;
}

export interface PrepareSlice {
  selectedFile: File | null;
  mediaSelectionVersion: number;
  project: ProjectMetadata & { previewUrl?: string };
  languages: {
    source: { code: string; name: string; flag: string; autoDetected: boolean };
    target: { code: string; name: string };
    timingMode: string;
  };
  engines: {
    speakerDiarization: boolean;
    speakerCount: number;
    ocrSlideEngine: boolean;
  };
  backend: {
    ready: boolean;
    error: string | null;
    mediaId: string | null;
    status: 'idle' | 'analyzing' | 'ready' | 'submitting' | 'queued' | 'running' | 'completed' | 'failed';
    message: string;
    options: BackendOptions;
    config: {
      recognType: number;
      translateType: number;
      translationMode: string;
      ttsType: number;
      modelName: string;
      voiceRole: string;
      useCuda: boolean;
      deepgramOptions: DeepgramConfigOptions;
    };
  };
  ocrCrop: OcrCropState;

  initializeBackend: () => Promise<void>;
  selectMedia: (file: File) => Promise<void>;
  updateSourceLanguage: (code: string, name: string) => void;
  updateTargetLanguage: (code: string, name: string) => void;
  updateAsrProvider: (recognType: number, modelName: string) => void;
  updateTranslationProvider: (translateType: number) => void;
  updateTranslationMode: (mode: string) => void;
  updateDeepgramOptions: (opts: Partial<DeepgramConfigOptions>) => void;
  updateUseCuda: (useCuda: boolean) => void;
  updateTimingMode: (timingMode: string) => void;
  updateEngineConfig: (key: 'speakerDiarization' | 'speakerCount' | 'ocrSlideEngine', value: any) => void;
  setOcrCropRoi: (roi: [number, number, number, number]) => void;
  setOcrCropActive: (active: boolean, segmentId?: number | null) => void;
}

export const createPrepareSlice: StateCreator<any, [], [], PrepareSlice> = (set, get) => ({
  selectedFile: null,
  mediaSelectionVersion: 0,
  project: {
    filename: 'Select a video to begin',
    format: '—',
    resolution: '—',
    fps: '—',
    duration: '00:00.000',
    durationSec: 0,
    fileSize: '—',
    videoCodec: '—',
    audioCodec: '—',
    bitrate: 'Not reported',
    hasAudio: false,
    hasVideo: false,
    verified: false,
    lastSaved: 'Just now',
  },
  languages: {
    source: { code: 'zh-cn', name: 'Simplified Chinese', flag: '', autoDetected: false },
    target: { code: 'vi', name: 'Vietnamese' },
    timingMode: 'voice',
  },
  engines: {
    speakerDiarization: false,
    speakerCount: 0,
    ocrSlideEngine: true,
  },
  backend: {
    ready: false,
    error: null,
    mediaId: null,
    status: 'idle',
    message: 'Choose a video to start',
    options: {
      languages: [],
      asrProviders: [],
      translationProviders: [],
      translationModes: [],
      voices: [],
    },
    config: {
      recognType: 1,
      translateType: 0,
      translationMode: 'srt',
      ttsType: 2,
      modelName: 'nova-3',
      voiceRole: '',
      useCuda: false,
      deepgramOptions: {
        utt_split: 0.8,
        diarize_model: 'latest',
        smart_format: true,
        punctuate: true,
        paragraphs: true,
        utterances: true,
        extra: '',
      },
    },
  },
  ocrCrop: {
    active: false,
    segmentId: null,
    roi: [0.05, 0.75, 0.9, 0.2],
    loading: false,
    error: null,
  },

  initializeBackend: async () => {
    try {
      const opts = await fetchOptions();
      set((state: any) => {
        const isReady = state.backend?.ready;
        return {
          backend: {
            ...state.backend,
            ready: true,
            options: opts,
            config: {
              ...state.backend.config,
              recognType: isReady ? state.backend.config.recognType : (opts.defaults?.recognType ?? state.backend.config.recognType),
              modelName: isReady ? state.backend.config.modelName : (opts.defaults?.modelName ?? state.backend.config.modelName),
              translateType: isReady ? state.backend.config.translateType : (opts.defaults?.translateType ?? state.backend.config.translateType),
              translationMode: isReady ? state.backend.config.translationMode : (opts.defaults?.translationMode ?? state.backend.config.translationMode),
            },
          },
        };
      });
    } catch (err: any) {
      set((state: any) => ({
        backend: {
          ...state.backend,
          error: `Backend unavailable: ${err.message}`,
        },
      }));
    }
  },

  selectMedia: async (file: File) => {
    if (!file) return;
    const version = (get().mediaSelectionVersion || 0) + 1;
    const previewUrl = URL.createObjectURL(file);

    set((state: any) => ({
      selectedFile: file,
      mediaSelectionVersion: version,
      backend: {
        ...state.backend,
        status: 'analyzing',
        message: 'Uploading and inspecting source media…',
        mediaId: null,
        error: null,
      },
      project: {
        ...state.project,
        filename: file.name,
        fileSize: formatBytes(file.size),
        format: file.name.includes('.') ? file.name.split('.').pop()!.toUpperCase() : 'Media',
        previewUrl,
        verified: false,
      },
      playback: {
        ...state.playback,
        currentTime: 0,
        formattedTime: '00:00.000',
        isPlaying: false,
      },
    }));

    try {
      const media = await uploadMedia(file);
      if (get().mediaSelectionVersion !== version) return;

      const durSec = media.durationMs ? media.durationMs / 1000 : 0;
      const persistentPreviewUrl = `/api/media/${media.id}/file`;
      set((state: any) => ({
        backend: {
          ...state.backend,
          status: 'ready',
          message: 'Media verified — ready to process',
          mediaId: media.id,
        },
        project: {
          ...state.project,
          filename: media.filename,
          fileSize: formatBytes(media.sizeBytes),
          durationSec: durSec,
          duration: formatTimecode(durSec),
          resolution: media.resolution || 'Audio only',
          fps: media.fps ? `${Number(media.fps).toFixed(2)} fps` : '—',
          videoCodec: media.videoCodec || '—',
          format: media.container || state.project.format,
          bitrate: media.bitrate ? `${(Number(media.bitrate) / 1_000_000).toFixed(2)} Mbps` : 'Not reported',
          audioCodec: media.audioCodec || '—',
          hasAudio: media.hasAudio,
          hasVideo: media.hasVideo,
          verified: true,
          previewUrl: persistentPreviewUrl,
        },
        playback: {
          ...state.playback,
          duration: durSec,
        },
      }));

      // If no active project, or if current active project already has segments / was past step 1, create a new one
      const curProjId = get().activeProjectId;
      const hasExistingProgress = (get().segments?.length || 0) > 0 || get().currentStep > 1;
      if (!curProjId || hasExistingProgress) {
        await get().createNewProject(media.filename, media.id, durSec);
      }
      get().triggerAutosave();
    } catch (err: any) {
      if (get().mediaSelectionVersion !== version) return;
      set((state: any) => ({
        backend: {
          ...state.backend,
          status: 'failed',
          error: err.message,
          message: 'Media inspection failed',
        },
      }));
    }
  },

  updateSourceLanguage: (code: string, name: string) => {
    set((state: any) => ({
      languages: {
        ...state.languages,
        source: { code, name, flag: '', autoDetected: false },
      },
    }));
    get().triggerAutosave();
  },

  updateTargetLanguage: (code: string, name: string) => {
    set((state: any) => ({
      languages: {
        ...state.languages,
        target: { code, name },
      },
    }));
    get().loadVoices?.();
    get().triggerAutosave();
  },

  updateAsrProvider: (recognType: number, modelName: string) => {
    set((state: any) => ({
      backend: {
        ...state.backend,
        config: {
          ...state.backend.config,
          recognType,
          modelName,
        },
      },
    }));
    get().triggerAutosave();
  },

  updateTranslationProvider: (translateType: number) => {
    set((state: any) => ({
      backend: {
        ...state.backend,
        config: {
          ...state.backend.config,
          translateType,
        },
      },
    }));
    get().triggerAutosave?.();
  },

  updateTranslationMode: (translationMode: string) => {
    set((state: any) => ({
      backend: {
        ...state.backend,
        config: {
          ...state.backend.config,
          translationMode,
        },
      },
    }));
    get().triggerAutosave?.();
  },

  updateDeepgramOptions: (opts: Partial<DeepgramConfigOptions>) => {
    set((state: any) => ({
      backend: {
        ...state.backend,
        config: {
          ...state.backend.config,
          deepgramOptions: {
            ...state.backend.config.deepgramOptions,
            ...opts,
          },
        },
      },
    }));
    get().triggerAutosave?.();
  },

  updateUseCuda: (useCuda: boolean) => {
    set((state: any) => ({
      backend: {
        ...state.backend,
        config: {
          ...state.backend.config,
          useCuda,
        },
      },
    }));
    get().triggerAutosave?.();
  },

  updateTimingMode: (timingMode: string) => {
    set((state: any) => ({
      languages: {
        ...state.languages,
        timingMode,
      },
    }));
    get().triggerAutosave?.();
  },

  updateEngineConfig: (key: 'speakerDiarization' | 'speakerCount' | 'ocrSlideEngine', value: any) => {
    set((state: any) => ({
      engines: {
        ...state.engines,
        [key]: value,
      },
    }));
    get().triggerAutosave();
  },

  setOcrCropRoi: (roi: [number, number, number, number]) => {
    set((state: any) => ({
      ocrCrop: {
        ...state.ocrCrop,
        roi,
      },
    }));
    get().triggerAutosave();
  },

  setOcrCropActive: (active: boolean, segmentId: number | null = null) => {
    set((state: any) => ({
      ocrCrop: {
        ...state.ocrCrop,
        active,
        segmentId,
      },
    }));
  },
});
