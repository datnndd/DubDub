export interface JobRecord {
  jobId: string;
  stage: string | null;
  status: 'idle' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number | null;
  message: string;
  projectId?: string;
  jobType?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface JobEvent {
  seq: number;
  job_id: string;
  event_type: string;
  progress: number;
  message: string;
  created_at: string;
}
