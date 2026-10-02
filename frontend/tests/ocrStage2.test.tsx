import React from 'react';
import { beforeEach, describe, expect, test } from 'bun:test';
import { renderToStaticMarkup } from 'react-dom/server';
import { Stage2OcrDialog, roiFromDrag } from '../src/components/Stage2OcrDialog';
import { Stage2ReviewTranscript, applyExtractedOcrResult, extractSelectedOcrSegments, selectedOcrSegments } from '../src/screens/Stage2ReviewTranscript';
import { useDubDubStore } from '../src/store';

const segment = {
  id: 1, speakerId: 'spk_1', startTime: '00:01', endTime: '00:02',
  startSec: 1, endSec: 2, sourceText: 'old source', targetText: 'old translation',
  previewAudioUrl: '/preview.wav', previewAudioId: 'prev_123456789abc',
};

beforeEach(() => {
  useDubDubStore.setState({
    activeProjectId: null,
    searchQuery: '',
    segments: [segment, { ...segment, id: 2, sourceText: 'other source' }],
    backend: { ...useDubDubStore.getState().backend, mediaId: 'media-1' },
    languages: { ...useDubDubStore.getState().languages, source: { code: 'en', name: 'English' } },
  });
});

describe('Stage 2 segment OCR', () => {
  test('successful OCR immediately replaces only the matching source cue', async () => {
    const result = await applyExtractedOcrResult(
      { segment, text: 'Xin chào', confidence: 0.9 },
      () => useDubDubStore.getState().segments,
      useDubDubStore.getState().applyOcrText,
    );
    expect(result.applied).toBe(true);
    expect(useDubDubStore.getState().segments[0]).toMatchObject({
      id: 1, startSec: 1, endSec: 2, sourceText: 'Xin chào', targetText: '',
    });
    expect(useDubDubStore.getState().segments[1].sourceText).toBe('other source');
  });

  test('empty, failed, and stale OCR results never replace a cue', async () => {
    const apply = useDubDubStore.getState().applyOcrText;
    const current = () => useDubDubStore.getState().segments;
    expect((await applyExtractedOcrResult({ segment, text: '' }, current, apply)).applied).toBe(false);
    expect((await applyExtractedOcrResult({ segment, error: 'OCR failed' }, current, apply)).applied).toBe(false);
    useDubDubStore.setState({ segments: [{ ...segment, endSec: 3 }] });
    const stale = await applyExtractedOcrResult({ segment, text: 'Wrong interval' }, current, apply);
    expect(stale.applied).toBe(false);
    expect(stale.error).toContain('timing changed');
    expect(current()[0].sourceText).toBe('old source');
  });

  test('applied OCR waits for the serialized project save and reports save failures', async () => {
    const originalFetch = globalThis.fetch;
    const requests: any[] = [];
    useDubDubStore.setState({ activeProjectId: 'project-ocr' });
    globalThis.fetch = (async (url: string, options: RequestInit) => {
      requests.push({ url, body: JSON.parse(String(options.body)) });
      return new Response(JSON.stringify({ detail: 'SRT write failed' }),
        { status: 500, headers: { 'Content-Type': 'application/json' } });
    }) as typeof fetch;
    try {
      const result = await applyExtractedOcrResult({ segment, text: 'OCR text' },
        () => useDubDubStore.getState().segments, useDubDubStore.getState().applyOcrText);
      expect(requests).toHaveLength(1);
      expect(requests[0].url).toBe('/api/projects/project-ocr');
      expect(requests[0].body.state.segments[0].sourceText).toBe('OCR text');
      expect(result.error).toContain('SRT write failed');
      expect(result.applied).toBe(false);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test('crop drag converts video-relative points to normalized ROI', () => {
    expect(roiFromDrag([0.9, 0.95], [0.1, 0.75])).toEqual([0.1, 0.75, 0.8, 0.19999999999999996]);
    expect(roiFromDrag([-1, 0.5], [2, 0.8])).toEqual([0, 0.5, 1, 0.30000000000000004]);
  });

  test('request includes source language and the selected interval', async () => {
    const originalFetch = globalThis.fetch;
    let payload: any;
    globalThis.fetch = (async (_url: string, options: RequestInit) => {
      payload = JSON.parse(String(options.body));
      return new Response(JSON.stringify({ ok: true, text: 'recognized', confidence: 0.92 }),
        { status: 200, headers: { 'Content-Type': 'application/json' } });
    }) as typeof fetch;
    try {
      const result = await useDubDubStore.getState().extractOcrForSegment(1, [0.1, 0.7, 0.8, 0.2]);
      expect(payload).toEqual({ mediaId: 'media-1', roi: [0.1, 0.7, 0.8, 0.2], startSec: 1, endSec: 2, segmentId: 1, language: 'en' });
      expect(result.text).toBe('recognized');
      expect(useDubDubStore.getState().segments[0].sourceText).toBe('old source');
    } finally { globalThis.fetch = originalFetch; }
  });

  test('applied OCR clears only the changed segment translation and voice preview', async () => {
    await useDubDubStore.getState().applyOcrText(1, 'recognized', 0.92);
    const [changed, other] = useDubDubStore.getState().segments;
    expect(changed.sourceText).toBe('recognized');
    expect(changed.targetText).toBe('');
    expect(changed.previewAudioId).toBeUndefined();
    expect(changed.ocrConfidence).toBe(0.92);
    expect(other.sourceText).toBe('other source');
    expect(other.targetText).toBe('old translation');
    expect(other.previewAudioId).toBe('prev_123456789abc');
  });

  test('failed request is surfaced and leaves both segments unchanged', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = (async () => new Response(JSON.stringify({ detail: 'PaddleOCR unavailable' }),
      { status: 400, headers: { 'Content-Type': 'application/json' } })) as typeof fetch;
    try {
      await expect(useDubDubStore.getState().extractOcrForSegment(1, [0.1, 0.7, 0.8, 0.2])).rejects.toThrow('PaddleOCR unavailable');
      expect(useDubDubStore.getState().segments[0].sourceText).toBe('old source');
    } finally { globalThis.fetch = originalFetch; }
  });

  test('OCR dialog explains automatic updates, empty results, loading, and errors', () => {
    let closed = 0;
    const props = { segment, videoUrl: '/api/media/media-1/file', roi: [0.05, 0.75, 0.9, 0.2] as [number, number, number, number],
      onRoiChange: () => {}, onExtract: () => {},
      onClose: () => { closed++; }, loading: false, result: { text: '', confidence: 0 }, error: null };
    const empty = renderToStaticMarkup(<Stage2OcrDialog {...props} />);
    expect(empty).toContain('No text was found');
    expect(empty).not.toContain('Apply to Source Text');
    expect(empty).toContain('automatically');
    const loading = renderToStaticMarkup(<Stage2OcrDialog {...props} loading result={null} />);
    expect(loading).toContain('Reading video frames');
    const failure = renderToStaticMarkup(<Stage2OcrDialog {...props} error="OCR unavailable" result={null} />);
    expect(failure).toContain('OCR unavailable');
    const applied = renderToStaticMarkup(<Stage2OcrDialog {...props} result={{ text: 'recognized', confidence: 0.92, applied: true }} />);
    expect(applied).toContain('Source subtitle updated and saved');
    expect(applied).toContain('92% confidence');
    props.onClose();
    expect(closed).toBe(1);
    expect(useDubDubStore.getState().segments[0].sourceText).toBe('old source');
  });

  test('Stage 2 clearly offers selected-segment OCR alongside single-segment OCR', () => {
    const html = renderToStaticMarkup(<Stage2ReviewTranscript />);
    expect(html).toContain('Run OCR on Selected Segments');
    expect(html).toContain('Select segment checkboxes below');
    expect(html).toContain('Select segment 1 for OCR');
    expect(html).toContain('Select segment 2 for OCR');
    expect(html).toContain('OCR Extract');
  });

  test('selected OCR requests only checked intervals and applies successes immediately', async () => {
    const segments = [segment, { ...segment, id: 2, startSec: 2, endSec: 3 }, { ...segment, id: 3, startSec: 3, endSec: 4, sourceText: 'hidden source' }];
    useDubDubStore.setState({ segments });
    const snapshot = selectedOcrSegments(segments, [1, 3]);
    expect(snapshot.map((item) => item.id)).toEqual([1, 3]);
    useDubDubStore.setState({ searchQuery: 'old source' });
    expect(renderToStaticMarkup(<Stage2ReviewTranscript />)).not.toContain('Select segment 3 for OCR');
    const originalFetch = globalThis.fetch;
    const payloads: any[] = [];
    const results: any[] = [];
    globalThis.fetch = (async (_url: string, options: RequestInit) => {
      const payload = JSON.parse(String(options.body));
      payloads.push(payload);
      if (payload.segmentId === 3) return new Response(JSON.stringify({ detail: 'OCR unavailable for this interval' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } });
      return new Response(JSON.stringify({ ok: true, text: 'FIRST', confidence: 0.9 }),
        { status: 200, headers: { 'Content-Type': 'application/json' } });
    }) as typeof fetch;
    try {
      await extractSelectedOcrSegments(snapshot, [0.1, 0.7, 0.8, 0.2],
        useDubDubStore.getState().extractOcrForSegment, async (entry) => {
          results.push(await applyExtractedOcrResult(entry,
            () => useDubDubStore.getState().segments, useDubDubStore.getState().applyOcrText));
        }, () => true);
      expect(payloads.map(({ segmentId, startSec, endSec, language }) => ({ segmentId, startSec, endSec, language })))
        .toEqual([{ segmentId: 1, startSec: 1, endSec: 2, language: 'en' },
          { segmentId: 3, startSec: 3, endSec: 4, language: 'en' }]);
      expect(results.map(({ segment, text, error }) => ({ id: segment.id, text, error })))
        .toEqual([{ id: 1, text: 'FIRST', error: undefined },
          { id: 3, text: undefined, error: 'OCR unavailable for this interval' }]);
      expect(useDubDubStore.getState().segments[0].sourceText).toBe('FIRST');
      expect(useDubDubStore.getState().segments[1].sourceText).toBe('old source');
      expect(useDubDubStore.getState().segments[2].sourceText).toBe('hidden source');
    } finally { globalThis.fetch = originalFetch; }
  });

  test('cancel stops later requests and keeps an already applied result', async () => {
    const requested: number[] = [];
    const results: number[] = [];
    let active = true;
    await extractSelectedOcrSegments([segment, { ...segment, id: 2 }], [0, 0.7, 1, 0.2],
      async (id) => { requested.push(id); return { text: 'found' }; },
      async (entry) => {
        await applyExtractedOcrResult(entry, () => useDubDubStore.getState().segments,
          useDubDubStore.getState().applyOcrText);
        results.push(entry.segment.id);
        active = false;
      }, () => active);
    expect(requested).toEqual([1]);
    expect(results).toEqual([1]);
    expect(useDubDubStore.getState().segments[0].sourceText).toBe('found');
    expect(useDubDubStore.getState().segments[1].sourceText).toBe('other source');
  });

  test('batch results show applied, empty, failed, and stale segments without confirmation', () => {
    const later = { ...segment, id: 2, startSec: 2, endSec: 3 };
    const stale = { ...segment, id: 3, startSec: 3, endSec: 4 };
    const html = renderToStaticMarkup(<Stage2OcrDialog segment={segment} batchSegments={[segment, later, stale]}
      batchResults={[{ segment, text: 'FIRST', confidence: 0.9, applied: true }, { segment: later, text: '' }, { segment: stale, text: 'THIRD', error: 'This segment or its timing changed. Run OCR again.' }]}
      currentSegments={[segment, later, { ...stale, endSec: 5 }]} progress={3} videoUrl="/api/media/media-1/file"
      roi={[0.05, 0.75, 0.9, 0.2]} onRoiChange={() => {}} onExtract={() => {}}
      onClose={() => {}} loading={false} result={null} error={null} />);
    expect(html).toContain('Segment 1 · 1.00s–2.00s');
    expect(html).toContain('No text was found in this time range');
    expect(html).toContain('This segment or its timing changed');
    expect(html).toContain('Source subtitle updated and saved');
    expect(html).not.toContain('Apply Reviewed Text');
    expect(useDubDubStore.getState().segments[0].sourceText).toBe('old source');
  });
});
