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
  createNewProject: (name?: string) => Promise<string>;
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
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('dubdub_active_project_id', id);
      }
      set({ activeProjectId: id, drawerOpen: false });
      if (project.state_json) {
        try {
          const parsed = JSON.parse(project.state_json);
          set((state: any) => ({
            ...state,
            ...parsed,
            activeProjectId: id,
            drawerOpen: false,
          }));
        } catch (_) {}
      }
    } catch (err) {
      console.error('Failed to select project:', err);
    }
  },

  createNewProject: async (name: string = 'Untitled Video Project') => {
    try {
      const proj = await createProject({ name });
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('dubdub_active_project_id', proj.id);
      }
      set({ activeProjectId: proj.id, currentStep: 1 });
      await get().loadProjects();
      return proj.id;
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
      subtitleStyles: currentState.subtitleStyles,
      editVideo: {
        audioMix: currentState.editVideo?.audioMix,
        activeTab: currentState.editVideo?.activeTab,
      },
      currentStep: currentState.currentStep,
    };
    updateProjectState(id, snapshot, currentState.currentStep).catch((err) => {
      console.warn('Autosave failed:', err);
    });
  },
});
