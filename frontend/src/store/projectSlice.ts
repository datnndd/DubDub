import { StateCreator } from 'zustand';
import type { ProjectRecord } from '../types/project';
import { fetchProjects, fetchProject, createProject, deleteProject as apiDeleteProject, updateProjectState } from '../api/projects';

export interface ProjectSlice {
  activeProjectId: string | null;
  drawerOpen: boolean;
  projectsList: ProjectRecord[];
  currentStep: number;
  maxUnlockedStep: number;
  
  setStep: (step: number) => void;
  setDrawerOpen: (open: boolean) => void;
  loadProjects: () => Promise<void>;
  selectProject: (id: string) => Promise<void>;
  createNewProject: (name?: string, mediaId?: string, duration?: number) => Promise<string>;
  deleteProjectById: (id: string) => Promise<void>;
  triggerAutosave: () => void;
}

export function normalizeLanguages(incoming: any, fallback?: any) {
  const defaultFallback = {
    source: { code: 'zh-cn', name: 'Simplified Chinese', flag: '', autoDetected: false },
    target: { code: 'vi', name: 'Vietnamese' },
    timingMode: 'voice',
  };
  const base = fallback || defaultFallback;
  if (!incoming || typeof incoming !== 'object') {
    return {
      source: {
        code: base?.source?.code || 'zh-cn',
        name: base?.source?.name || 'Simplified Chinese',
        flag: base?.source?.flag || '',
        autoDetected: Boolean(base?.source?.autoDetected),
      },
      target: {
        code: base?.target?.code || 'vi',
        name: base?.target?.name || 'Vietnamese',
      },
      timingMode: base?.timingMode || 'voice',
    };
  }

  let sourceCode = base?.source?.code || 'zh-cn';
  let sourceName = base?.source?.name || 'Simplified Chinese';
  let sourceFlag = base?.source?.flag || '';
  let autoDetected = Boolean(base?.source?.autoDetected);

  if (typeof incoming.source === 'string') {
    sourceCode = incoming.source;
    sourceName = incoming.source;
  } else if (incoming.source && typeof incoming.source === 'object') {
    sourceCode = incoming.source.code || incoming.source_code || sourceCode;
    sourceName = incoming.source.name || sourceName;
    sourceFlag = incoming.source.flag || '';
    autoDetected = Boolean(incoming.source.autoDetected);
  } else if (incoming.source_code) {
    sourceCode = incoming.source_code;
  }

  let targetCode = base?.target?.code || 'vi';
  let targetName = base?.target?.name || 'Vietnamese';

  if (typeof incoming.target === 'string') {
    targetCode = incoming.target;
    targetName = incoming.target;
  } else if (incoming.target && typeof incoming.target === 'object') {
    targetCode = incoming.target.code || incoming.target_code || targetCode;
    targetName = incoming.target.name || targetName;
  } else if (incoming.target_code) {
    targetCode = incoming.target_code;
  }

  return {
    source: {
      code: sourceCode,
      name: sourceName,
      flag: sourceFlag,
      autoDetected,
    },
    target: {
      code: targetCode,
      name: targetName,
    },
    timingMode: incoming.timingMode || base?.timingMode || 'voice',
  };
}

export const createProjectSlice: StateCreator<any, [], [], ProjectSlice> = (set, get) => ({
  activeProjectId: typeof localStorage !== 'undefined' ? localStorage.getItem('dubdub_active_project_id') : null,
  drawerOpen: false,
  projectsList: [],
  currentStep: 1,
  maxUnlockedStep: 4,

  setStep: (step: number) => {
    if (step < 1 || step > 4) return;
    set((state: any) => ({
      currentStep: step,
      maxUnlockedStep: Math.max(state.maxUnlockedStep || 1, step),
    }));
    get().triggerAutosave();
  },

  setDrawerOpen: (open: boolean) => set({ drawerOpen: open }),

  loadProjects: async () => {
    try {
      const list = await fetchProjects();
      set({ projectsList: list });
    } catch (err) {
      console.warn('Failed to load projects list:', err);
    }
  },

  selectProject: async (id: string) => {
    try {
      const project = await fetchProject(id);
      if (!project) {
        if (typeof localStorage !== 'undefined') {
          localStorage.removeItem('dubdub_active_project_id');
        }
        set((state: any) => ({ ...state, activeProjectId: null }));
        return;
      }
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('dubdub_active_project_id', id);
      }
      let stateData: any = (project as any).state || null;
      if (!stateData && project.state_json) {
        try {
          stateData = typeof project.state_json === 'string' ? JSON.parse(project.state_json) : project.state_json;
        } catch (e) {
          console.warn('Failed to parse project.state_json:', e);
          stateData = null;
        }
      }
      const targetStep = stateData?.currentStep || project.stage || 1;
      const mediaId = (project as any).media_id || stateData?.backend?.mediaId || null;
      let resolvedPreviewUrl: string | undefined = undefined;
      if (mediaId) {
        const candidateUrl = stateData?.project?.previewUrl;
        resolvedPreviewUrl = (candidateUrl && !candidateUrl.startsWith('blob:'))
          ? candidateUrl
          : `/api/media/${mediaId}/file`;
      }
      const isVerified = Boolean(mediaId && (stateData?.project?.verified ?? true));

      const rawSegments = Array.isArray(stateData?.segments) ? stateData.segments : [];
      const normalizedSegments = rawSegments.map((seg: any, idx: number) => ({
        ...seg,
        id: seg?.id ?? idx + 1,
        sourceText: String(seg?.sourceText ?? seg?.text ?? ''),
        targetText: String(seg?.targetText ?? ''),
        speakerId: String(seg?.speakerId ?? seg?.speakerLabel ?? seg?.speaker ?? 'spk_1'),
        speakerName: String(seg?.speakerName ?? (seg?.speakerLabel ? `Speaker ${seg.speakerLabel}` : 'Speaker 1')),
      }));

      const rawSpeakers = Array.isArray(stateData?.speakers) ? stateData.speakers : [];
      const normalizedSpeakers = rawSpeakers.map((spk: any, idx: number) => ({
        ...spk,
        id: String(spk?.id ?? `spk_${idx + 1}`),
        name: String(spk?.name ?? `Speaker ${idx + 1}`),
        code: String(spk?.code || spk?.id || `S${idx + 1}`).slice(0, 2).toUpperCase(),
      }));

      const rawOverrides = stateData?.segmentVoiceOverrides || {};
      const mergedOverrides: Record<number, string> = { ...rawOverrides };
      normalizedSegments.forEach((seg: any) => {
        if (seg.id && seg.voiceOverride && !mergedOverrides[seg.id]) {
          mergedOverrides[seg.id] = seg.voiceOverride;
        }
      });

      set((state: any) => ({
        ...state,
        selectedFile: null,
        activeProjectId: id,
        currentStep: targetStep,
        maxUnlockedStep: Math.max(project.stage || 1, targetStep),
        drawerOpen: false,
        segments: normalizedSegments,
        transcriptOptions: stateData?.transcriptOptions || null,
        selectedSegmentOption: stateData?.selectedSegmentOption || 'utterances',
        speakers: normalizedSpeakers,
        speakerVoiceMap: stateData?.speakerVoiceMap || {},
        segmentVoiceOverrides: mergedOverrides,
        dubbingStatus: stateData?.dubbingStatus || 'idle',
        tuning: stateData?.tuning ? { ...state.tuning, ...stateData.tuning } : state.tuning,
        jobStatus: 'idle',
        jobProgress: null,
        jobStage: null,
        jobMessage: 'Ready to process',
        backend: {
          ...state.backend,
          mediaId: mediaId,
          status: mediaId ? 'ready' : 'idle',
          error: null,
          message: '',
          config: {
            ...state.backend?.config,
            ...(stateData?.backend?.config || {}),
          },
        },
        languages: normalizeLanguages(stateData?.languages, state.languages),
        engines: {
          ...state.engines,
          ...(stateData?.engines || {}),
        },
        project: {
          filename: project.name || 'Untitled Video Project',
          format: '—',
          resolution: '—',
          fps: '—',
          duration: '00:00.000',
          durationSec: 0,
          fileSize: '—',
          videoCodec: '—',
          audioCodec: '—',
          bitrate: 'Not reported',
          hasAudio: isVerified,
          hasVideo: isVerified,
          lastSaved: 'Just now',
          ...(stateData?.project || {}),
          previewUrl: resolvedPreviewUrl,
          verified: isVerified,
        },
      }));
    } catch (err) {
      console.error('Failed to select project:', err);
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem('dubdub_active_project_id');
      }
      set((state: any) => ({ ...state, activeProjectId: null }));
    }
  },

  createNewProject: async (name: string = 'Untitled Video Project', mediaId?: string, duration?: number) => {
    try {
      const proj = await createProject({ name, mediaId, duration });
      const newId = proj?.id;
      if (newId) {
        await get().selectProject(newId);
      }
      await get().loadProjects();
      return newId || '';
    } catch (err) {
      console.error('Failed to create new project:', err);
      return '';
    }
  },

  deleteProjectById: async (id: string) => {
    try {
      await apiDeleteProject(id);
      if (get().activeProjectId === id) {
        set({ activeProjectId: null });
        if (typeof localStorage !== 'undefined') {
          localStorage.removeItem('dubdub_active_project_id');
        }
      }
      await get().loadProjects();
    } catch (err) {
      console.error('Failed to delete project:', err);
    }
  },

  triggerAutosave: () => {
    const id = get().activeProjectId;
    if (!id) return;
    const currentState = get();
    const mediaId = currentState.backend?.mediaId || null;
    // Exclude transient file objects and dead blob URLs from autosave JSON
    const snapshot = {
      backend: {
        mediaId,
        config: currentState.backend?.config,
      },
      project: {
        ...currentState.project,
        previewUrl: mediaId ? `/api/media/${mediaId}/file` : undefined,
      },
      languages: currentState.languages,
      engines: currentState.engines,
      speakers: currentState.speakers,
      speakerVoiceMap: currentState.speakerVoiceMap,
      segmentVoiceOverrides: currentState.segmentVoiceOverrides,
      dubbingStatus: currentState.dubbingStatus,
      tuning: currentState.tuning,
      segments: currentState.segments,
      transcriptOptions: currentState.transcriptOptions,
      selectedSegmentOption: currentState.selectedSegmentOption,
      subtitleStyles: currentState.subtitleStyles,
      editVideo: {
        audioMix: currentState.editVideo?.audioMix,
        activeTab: currentState.editVideo?.activeTab,
      },
      currentStep: currentState.currentStep,
    };
    updateProjectState(id, snapshot, currentState.currentStep, mediaId || undefined)
      .then(() => {
        const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        set((s: any) => ({
          project: {
            ...s.project,
            lastSaved: timeStr,
          },
        }));
      })
      .catch((err) => {
        console.warn('Autosave failed:', err);
      });
  },
});
