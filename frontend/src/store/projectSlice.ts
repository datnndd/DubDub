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

export const createProjectSlice: StateCreator<any, [], [], ProjectSlice> = (set, get) => ({
  activeProjectId: typeof localStorage !== 'undefined' ? localStorage.getItem('dubdub_active_project_id') : null,
  drawerOpen: false,
  projectsList: [],
  currentStep: 1,
  maxUnlockedStep: 4,

  setStep: (step: number) => {
    if (step < 1 || step > 4) return;
    set({ currentStep: step });
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
      if (!project) return;
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('dubdub_active_project_id', id);
      }
      const stateData = (project as any).state || (project.state_json ? JSON.parse(project.state_json) : null);
      const targetStep = stateData?.currentStep || project.stage || 1;
      const mediaId = (project as any).media_id || stateData?.backend?.mediaId || null;
      const resolvedPreviewUrl = mediaId
        ? (stateData?.project?.previewUrl || `/api/media/${mediaId}/file`)
        : undefined;
      const isVerified = Boolean(mediaId && (stateData?.project?.verified ?? true));

      set((state: any) => ({
        ...state,
        selectedFile: null,
        activeProjectId: id,
        currentStep: targetStep,
        maxUnlockedStep: Math.max(project.stage || 1, targetStep),
        drawerOpen: false,
        segments: stateData?.segments || [],
        transcriptOptions: stateData?.transcriptOptions || null,
        selectedSegmentOption: stateData?.selectedSegmentOption || 'utterances',
        speakers: stateData?.speakers || [],
        speakerVoiceMap: stateData?.speakerVoiceMap || {},
        segmentVoiceOverrides: stateData?.segmentVoiceOverrides || {},
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
            ...state.backend.config,
            ...(stateData?.backend?.config || {}),
          },
        },
        languages: {
          ...state.languages,
          ...(stateData?.languages || {}),
        },
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
    // Exclude transient file objects from autosave JSON
    const snapshot = {
      project: currentState.project,
      languages: currentState.languages,
      engines: currentState.engines,
      speakers: currentState.speakers,
      speakerVoiceMap: currentState.speakerVoiceMap,
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
    updateProjectState(id, snapshot, currentState.currentStep)
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
