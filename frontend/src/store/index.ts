import { create } from 'zustand';
import { createProjectSlice, ProjectSlice } from './projectSlice';
import { createPlaybackSlice, PlaybackSlice } from './playbackSlice';
import { createPrepareSlice, PrepareSlice } from './prepareSlice';
import { createTranscriptSlice, TranscriptSlice } from './transcriptSlice';
import { createDubbingSlice, DubbingSlice } from './dubbingSlice';
import { createEditVideoSlice, EditVideoSlice } from './editVideoSlice';
import { createJobSlice, JobSlice } from './jobSlice';

export type AppStore = ProjectSlice &
  PlaybackSlice &
  PrepareSlice &
  TranscriptSlice &
  DubbingSlice &
  EditVideoSlice &
  JobSlice;

export const useDubDubStore = create<AppStore>()((set, get, api) => ({
  ...createProjectSlice(set, get, api),
  ...createPlaybackSlice(set, get, api),
  ...createPrepareSlice(set, get, api),
  ...createTranscriptSlice(set, get, api),
  ...createDubbingSlice(set, get, api),
  ...createEditVideoSlice(set, get, api),
  ...createJobSlice(set, get, api),
}));

export const useAppStore = useDubDubStore;
