import { StateCreator } from 'zustand';
import type { JobRecord } from '../types/job';
import { startJob, cancelJob, subscribeJobStream } from '../api/jobs';

export interface JobSlice {
  activeJob: JobRecord | null;
  jobProgress: number | null;
  jobStage: string | null;
  jobMessage: string;
  jobStatus: 'idle' | 'running' | 'completed' | 'failed' | 'cancelled';
  sseUnsubscribe: (() => void) | null;

  startPrepareJob: () => Promise<void>;
  subscribeToJob: (jobId: string) => void;
  cancelActiveJob: () => Promise<void>;
  clearJob: () => void;
}

export const createJobSlice: StateCreator<any, [], [], JobSlice> = (set, get) => ({
  activeJob: null,
  jobProgress: null,
  jobStage: null,
  jobMessage: 'Ready to process',
  jobStatus: 'idle',
  sseUnsubscribe: null,

  startPrepareJob: async () => {
    const backend = get().backend;
    const mediaId = backend?.mediaId;
    if (!mediaId) return;

    set({
      jobStatus: 'running',
      jobProgress: 0,
      jobStage: 'prepare',
      jobMessage: 'Initiating speech recognition & diarization…',
    });

    const body = {
      mediaId,
      projectId: get().activeProjectId,
      jobType: 'asr',
      options: {
        ...backend.config,
        projectId: get().activeProjectId,
        sourceLanguage: get().languages.source.code,
        targetLanguage: get().languages.target.code,
        timingMode: get().languages.timingMode,
        removeNoise: get().engines.removeNoise,
        speakerDiarization: get().engines.speakerDiarization,
        speakerCount: get().engines.speakerCount,
      },
    };

    try {
      const res = await startJob(body);
      if (res.jobId) {
        get().subscribeToJob(res.jobId);
      }
    } catch (err: any) {
      set({
        jobStatus: 'failed',
        jobMessage: err.message || 'Job submission failed',
      });
    }
  },

  subscribeToJob: (jobId: string) => {
    // Unsubscribe from previous if any
    if (get().sseUnsubscribe) {
      get().sseUnsubscribe();
    }

    set({
      activeJob: {
        jobId,
        stage: 'running',
        status: 'running',
        progress: 0,
        message: 'Processing job…',
      },
      jobStatus: 'running',
    });

    const unsub = subscribeJobStream(
      jobId,
      0,
      (evt) => {
        set({
          jobProgress: evt.progress,
          jobMessage: evt.message,
          jobStage: evt.event_type,
        });

        if (evt.event_type === 'done' || evt.event_type === 'completed') {
          set({
            jobStatus: 'completed',
            jobProgress: 100,
            jobMessage: evt.message || 'Job completed successfully',
          });
          // Unlock step 2 if we were on step 1
          if (get().currentStep === 1) {
            get().setStep(2);
          }
          get().triggerAutosave();
        } else if (evt.event_type === 'failed') {
          set({
            jobStatus: 'failed',
            jobMessage: evt.message || 'Job failed',
          });
        } else if (evt.event_type === 'cancelled') {
          set({
            jobStatus: 'cancelled',
            jobMessage: evt.message || 'Job cancelled',
          });
        }
      },
      (err) => {
        console.warn('SSE stream error:', err);
      }
    );

    set({ sseUnsubscribe: unsub });
  },

  cancelActiveJob: async () => {
    const job = get().activeJob;
    if (!job?.jobId) return;
    try {
      await cancelJob(job.jobId);
      set({
        jobStatus: 'cancelled',
        jobMessage: 'Job cancelled by user',
      });
    } catch (err) {
      console.warn('Failed to cancel job:', err);
    }
  },

  clearJob: () => {
    if (get().sseUnsubscribe) {
      get().sseUnsubscribe();
    }
    set({
      activeJob: null,
      jobProgress: null,
      jobStage: null,
      jobMessage: 'Ready',
      jobStatus: 'idle',
      sseUnsubscribe: null,
    });
  },
});
