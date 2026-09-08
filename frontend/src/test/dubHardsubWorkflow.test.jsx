import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAppStore } from '../store';

const api = vi.hoisted(() => ({
  dubUpload: vi.fn(), dubIngestUrl: vi.fn(), dubAbort: vi.fn(),
  dubCleanupSegments: vi.fn(), dubTranslate: vi.fn(), dubGenerate: vi.fn(),
  tasksStreamUrl: vi.fn((id) => `/tasks/${id}`), tasksCancel: vi.fn(),
  transcribeStreamUrl: vi.fn(), dubHardsubExtract: vi.fn(), dubImportSrt: vi.fn(),
}));
vi.mock('../api/dub', () => api);
vi.mock('../api/client', () => ({ apiPost: vi.fn(), apiFetch: vi.fn(), API: '' }));
import useDubWorkflow from '../hooks/useDubWorkflow';

const baseState = useAppStore.getState();
const original = [{ id: 0, start: 0, end: 1, text: 'existing' }];
const extracted = [{ id: 0, start: 0, end: 2, text: 'subtitle' }];
let streams;
let message;

function workflow() {
  return renderHook(() => useDubWorkflow({
    loadProjects: vi.fn(), loadProfiles: vi.fn(), loadDubHistory: vi.fn(),
    setLastGenFingerprints: vi.fn(),
  }));
}

beforeEach(() => {
  vi.clearAllMocks();
  useAppStore.setState({ ...baseState, dubJobId: 'job1', dubStep: 'editing', dubSegments: original }, true);
  streams = [];
  message = { type: 'hardsub_done', segments: extracted };
  vi.stubGlobal('EventSource', class {
    close = vi.fn();
    constructor(url) {
      streams.push(this);
      this.url = url;
      queueMicrotask(() => { if (message) this.onmessage?.({ data: JSON.stringify(message) }); });
    }
  });
});
afterEach(() => vi.unstubAllGlobals());

describe('subtitle extraction completion and recovery', () => {
  it('keeps scanner counters and original OCR text from progress events', async () => {
    message = null;
    api.dubHardsubExtract.mockResolvedValue({ task_id: 'hardsub_job1' });
    const { result } = workflow();
    let pending;
    await act(async () => { pending = result.current.handleHardsubExtract(); });
    await act(async () => {
      streams[0].onmessage({ data: JSON.stringify({
        type: 'hardsub_progress', decoded_frames: 8, ocr_calls: 3,
        skipped_frames: 5, cache_hits: 0, current_text: 'Hello, World!',
      }) });
    });
    expect(result.current.hardsubProgress).toMatchObject({
      decodedFrames: 8, ocrCalls: 3, skippedFrames: 5, cacheHits: 0,
      currentText: 'Hello, World!',
    });
    await act(async () => {
      streams[0].onmessage({ data: JSON.stringify({ type: 'hardsub_done', segments: extracted }) });
      await pending;
    });
  });

  it('applies an immediate soft-sub response without opening a task stream', async () => {
    api.dubHardsubExtract.mockResolvedValue({ segments: extracted, stats: { imported: 1 } });
    const { result } = workflow();
    await act(async () => { await result.current.handleHardsubExtract({ mode: 'auto' }); });
    expect(streams).toHaveLength(0);
    expect(useAppStore.getState().dubSegments[0].text).toBe('subtitle');
    expect(useAppStore.getState().dubStep).toBe('editing');
  });

  it('holds OCR output for Prepare review without replacing the editor transcript', async () => {
    api.dubHardsubExtract.mockResolvedValue({ segments: extracted });
    const { result } = workflow();
    let response;
    await act(async () => {
      response = await result.current.handleHardsubExtract({ mode: 'ocr', prepareReview: true });
    });
    expect(response.segments[0].text).toBe('subtitle');
    expect(useAppStore.getState().dubStep).toBe('prepare');
    expect(useAppStore.getState().dubSegments).toEqual(original);
  });

  it('tracks the OCR task so the cancel action targets the active operation', async () => {
    api.dubHardsubExtract.mockResolvedValue({ task_id: 'hardsub_job1' });
    let taskAtStreamOpen;
    api.tasksStreamUrl.mockImplementation((id) => {
      taskAtStreamOpen = useAppStore.getState().dubTaskId;
      return `/tasks/${id}`;
    });
    const { result } = workflow();
    await act(async () => { await result.current.handleHardsubExtract(); });
    expect(taskAtStreamOpen).toBe('hardsub_job1');
    expect(streams[0].close).toHaveBeenCalled();
  });

  it.each(['request', 'stream', 'cancel'])('returns to the existing editor after %s failure', async (failure) => {
    if (failure === 'request') api.dubHardsubExtract.mockRejectedValue(new Error('OCR unavailable'));
    else {
      api.dubHardsubExtract.mockResolvedValue({ task_id: 'hardsub_job1' });
      message = failure === 'cancel' ? { type: 'cancelled' } : { type: 'error', message: 'OCR unavailable' };
    }
    const { result } = workflow();
    await act(async () => { await result.current.handleHardsubExtract(); });
    expect(useAppStore.getState().dubStep).toBe('editing');
    expect(useAppStore.getState().dubSegments).toEqual(original);
    expect(result.current.hardsubRunning).toBe(false);
  });

  it('cancels the backend OCR task when the user aborts the stream', async () => {
    message = null;
    api.tasksCancel.mockResolvedValue({});
    api.dubHardsubExtract.mockResolvedValue({ task_id: 'hardsub_job1' });
    const { result } = workflow();
    let pending;
    await act(async () => { pending = result.current.handleHardsubExtract(); });
    expect(streams).toHaveLength(1);
    await act(async () => {
      await result.current.handleDubAbort();
      await pending;
    });
    expect(api.tasksCancel).toHaveBeenCalledWith('hardsub_job1');
    expect(streams[0].close).toHaveBeenCalled();
    expect(useAppStore.getState().dubStep).toBe('editing');
  });
});
