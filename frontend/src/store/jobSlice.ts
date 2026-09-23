import { StateCreator } from 'zustand';
import type { JobRecord } from '../types/job';
import { startJob, cancelJob, fetchJob, subscribeJobStream } from '../api/jobs';

export interface JobSlice {
  activeJob: JobRecord | null;
  jobProgress: number | null;
  jobStage: string | null;
  jobMessage: string;
  jobStatus: 'idle' | 'running' | 'completed' | 'failed' | 'cancelled';
  sseUnsubscribe: (() => void) | null;
  pollTimer: any;
  startTime: number | null;
  elapsedSeconds: number;

  startPrepareJob: () => Promise<void>;
  subscribeToJob: (jobId: string) => void;
  pollJob: (jobId: string) => Promise<void>;
  cancelActiveJob: () => Promise<void>;
  clearJob: () => void;
}

export function buildPrepareJobRequest(state: any) {
  return {
    mediaId: state.backend.mediaId,
    projectId: state.activeProjectId,
    jobType: 'asr',
    options: {
      ...state.backend.config,
      projectId: state.activeProjectId,
      sourceLanguage: state.languages.source.code,
      targetLanguage: state.languages.target.code,
      timingMode: state.languages.timingMode,
      removeNoise: state.engines.removeNoise,
      speakerDiarization: state.engines.speakerDiarization,
      speakerCount: state.engines.speakerCount,
    },
  };
}

export const createJobSlice: StateCreator<any, [], [], JobSlice> = (set, get) => ({
  activeJob: null,
  jobProgress: null,
  jobStage: null,
  jobMessage: 'Ready to process',
  jobStatus: 'idle',
  sseUnsubscribe: null,
  pollTimer: null,
  startTime: null,
  elapsedSeconds: 0,

  startPrepareJob: async () => {
    const backend = get().backend;
    const mediaId = backend?.mediaId;
    const project = get().project;

    if (!mediaId || !project.verified) {
      set({
        jobStatus: 'failed',
        jobMessage: 'Please upload and verify a video file first.',
      });
      return;
    }

    const provider = backend.options?.asrProviders?.find(
      (item: any) => item.recognType === Number(backend.config.recognType)
    );
    if (provider?.requiresSettings && !provider.configured) {
      set({
        jobStatus: 'failed',
        jobMessage: `Please configure ${provider.label} API key first.`,
      });
      return;
    }

    set({
      jobStatus: 'running',
      jobProgress: 0,
      jobStage: 'prepare',
      jobMessage: 'Initiating speech recognition & diarization…',
      startTime: Date.now(),
      elapsedSeconds: 0,
    });

    const body = buildPrepareJobRequest(get());

    try {
      const res = await startJob(body);
      const jobId = res.id || res.jobId;
      if (!jobId) {
        throw new Error('Server did not return a job ID');
      }

      if (res.status === 'succeeded') {
        if (Array.isArray(res.segments) && res.segments.length > 0) {
          get().setSegments(res.segments);
        }
        set({
          jobStatus: 'completed',
          jobProgress: 100,
          jobMessage: 'Job completed successfully',
        });
        if (get().currentStep === 1) {
          get().setStep(2);
        }
        get().triggerAutosave();
        return;
      }

      get().subscribeToJob(jobId);
    } catch (err: any) {
      set({
        jobStatus: 'failed',
        jobMessage: err.message || 'Job submission failed',
      });
    }
  },

  subscribeToJob: (jobId: string) => {
    // Clear previous subscription and poll timer
    if (get().sseUnsubscribe) {
      get().sseUnsubscribe();
    }
    if (get().pollTimer) {
      clearInterval(get().pollTimer);
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

    // Start 1s polling fallback
    const timer = setInterval(() => {
      get().pollJob(jobId);
    }, 1000);
    set({ pollTimer: timer });

    const handleSuccess = async (message?: string) => {
      if (get().pollTimer) {
        clearInterval(get().pollTimer);
        set({ pollTimer: null });
      }
      try {
        const fullJob = await fetchJob(jobId);
        if (fullJob?.segments && Array.isArray(fullJob.segments) && fullJob.segments.length > 0) {
          get().setSegments(fullJob.segments);
        }
      } catch (_) {}

      set({
        jobStatus: 'completed',
        jobProgress: 100,
        jobMessage: message || 'Speech recognition complete',
      });
      if (get().currentStep === 1) {
        get().setStep(2);
      }
      get().triggerAutosave();
    };

    const unsub = subscribeJobStream(
      jobId,
      0,
      async (payload) => {
        const st = get().startTime;
        if (st) {
          set({ elapsedSeconds: Math.round((Date.now() - st) / 1000) });
        }

        if (typeof payload.progress === 'number') {
          set({ jobProgress: payload.progress });
        }
        if (payload.stage) {
          set({ jobStage: payload.stage });
        }
        if (payload.message) {
          set({ jobMessage: payload.message });
        }

        if (payload.details?.segments && Array.isArray(payload.details.segments)) {
          get().setSegments(payload.details.segments);
        }

        const isSuccess =
          payload.status === 'succeeded' ||
          payload.kind === 'succeeded' ||
          payload.stage === 'task_done';
        const isFailed = payload.status === 'failed' || Boolean(payload.error);
        const isCancelled = payload.status === 'cancelled';

        if (isSuccess) {
          await handleSuccess(payload.message);
        } else if (isFailed) {
          if (get().pollTimer) {
            clearInterval(get().pollTimer);
            set({ pollTimer: null });
          }
          set({
            jobStatus: 'failed',
            jobMessage: payload.error || payload.message || 'Processing failed',
          });
        } else if (isCancelled) {
          if (get().pollTimer) {
            clearInterval(get().pollTimer);
            set({ pollTimer: null });
          }
          set({
            jobStatus: 'cancelled',
            jobMessage: 'Processing cancelled',
          });
        }
      },
      async (donePayload) => {
        await handleSuccess(donePayload?.message);
      },
      (err) => {
        console.warn('SSE stream notice:', err);
      }
    );

    set({ sseUnsubscribe: unsub });
  },

  pollJob: async (jobId: string) => {
    try {
      const st = get().startTime;
      if (st) {
        set({ elapsedSeconds: Math.round((Date.now() - st) / 1000) });
      }

      const job = await fetchJob(jobId);
      if (!job) return;

      if (typeof job.progress === 'number') {
        set({ jobProgress: job.progress });
      }
      if (job.stage) {
        set({ jobStage: job.stage });
      }
      if (job.message) {
        set({ jobMessage: job.message });
      }

      if (job.status === 'succeeded') {
        if (get().pollTimer) {
          clearInterval(get().pollTimer);
          set({ pollTimer: null });
        }
        if (get().sseUnsubscribe) {
          get().sseUnsubscribe();
          set({ sseUnsubscribe: null });
        }
        if (job.segments && Array.isArray(job.segments) && job.segments.length > 0) {
          get().setSegments(job.segments);
        }
        set({
          jobStatus: 'completed',
          jobProgress: 100,
          jobMessage: job.message || 'Speech recognition complete',
        });
        if (get().currentStep === 1) {
          get().setStep(2);
        }
        get().triggerAutosave();
      } else if (job.status === 'failed' || job.error) {
        if (get().pollTimer) {
          clearInterval(get().pollTimer);
          set({ pollTimer: null });
        }
        set({
          jobStatus: 'failed',
          jobMessage: job.error || job.message || 'Processing failed',
        });
      } else if (job.status === 'cancelled') {
        if (get().pollTimer) {
          clearInterval(get().pollTimer);
          set({ pollTimer: null });
        }
        set({
          jobStatus: 'cancelled',
          jobMessage: 'Processing cancelled',
        });
      }
    } catch (err) {
      console.warn('Poll job notice:', err);
    }
  },

  cancelActiveJob: async () => {
    const job = get().activeJob;
    if (!job?.jobId) return;
    if (get().pollTimer) {
      clearInterval(get().pollTimer);
      set({ pollTimer: null });
    }
    if (get().sseUnsubscribe) {
      get().sseUnsubscribe();
      set({ sseUnsubscribe: null });
    }
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
    if (get().pollTimer) {
      clearInterval(get().pollTimer);
    }
    set({
      activeJob: null,
      jobProgress: null,
      jobStage: null,
      jobMessage: 'Ready',
      jobStatus: 'idle',
      sseUnsubscribe: null,
      pollTimer: null,
      startTime: null,
      elapsedSeconds: 0,
    });
  },
});
