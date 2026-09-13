/**
 * Media utilities shared across the app.
 *
 * Extracted from App.jsx to reduce file size and enable independent testing.
 */
import { claimTrackedPlayback } from './playback';

// ── File → media URL ──────────────────────────────────────────────────
/**
 * Convert a File object to a media-safe URL.
 * The web runtime uses a browser object URL and revokes previous ones.
 */
export const fileToMediaUrl = async (file, prevUrls) => {
  // Revoke previous blob URLs if they exist
  if (prevUrls?.videoUrl?.startsWith('blob:')) URL.revokeObjectURL(prevUrls.videoUrl);
  if (prevUrls?.audioUrl?.startsWith('blob:')) URL.revokeObjectURL(prevUrls.audioUrl);

  const url = URL.createObjectURL(file);
  return { videoUrl: url, audioUrl: url };
};

// ── Blob audio playback ───────────────────────────────────────────────

/**
 * Downsample a decoded AudioBuffer into normalized [0..1] waveform peaks for
 * the global mini-player. Pure math — exported for unit tests.
 */
export const computePeaks = (audioBuffer, buckets = 240) => {
  try {
    const length = audioBuffer?.length || 0;
    if (!length) return null;
    const channels = Math.min(audioBuffer.numberOfChannels || 1, 2);
    const n = Math.min(buckets, length);
    const peaks = Array.from({ length: n }, () => 0);
    const bucketSize = length / n;
    // Stride within large buckets: peak *shape* is all the UI needs, and a
    // capped sample count keeps this O(buckets) even for hour-long renders.
    const step = Math.max(1, Math.floor(bucketSize / 64));
    for (let c = 0; c < channels; c++) {
      const data = audioBuffer.getChannelData(c);
      for (let i = 0; i < n; i++) {
        const start = Math.floor(i * bucketSize);
        const end = Math.min(length, Math.floor((i + 1) * bucketSize) || start + 1);
        let max = 0;
        for (let j = start; j < end; j += step) {
          const v = Math.abs(data[j]);
          if (v > max) max = v;
        }
        if (max > peaks[i]) peaks[i] = max;
      }
    }
    const top = Math.max(...peaks, 0.001);
    return peaks.map((p) => p / top);
  } catch {
    return null;
  }
};

// Best-effort peaks from an un-decoded blob (browser path). Uses an
// OfflineAudioContext so no audible/running context is spent on it. Peaks are
// a progressive enhancement — any failure just means the mini-player shows a
// plain progress bar.
const decodePeaksFromBlob = async (blob) => {
  try {
    const Offline = window.OfflineAudioContext || window.webkitOfflineAudioContext;
    if (!Offline) return null;
    const octx = new Offline(1, 1, 44100);
    const decoded = await octx.decodeAudioData(await blob.arrayBuffer());
    return computePeaks(decoded);
  } catch {
    return null;
  }
};

/**
 * Wire an HTMLAudioElement into the global playback manager as a tracked
 * 'output' playback: label + timeupdate-driven currentTime/duration + real
 * seek/pause/resume for the GlobalAudioPlayer bar.
 *
 * `onDone(reason)` fires exactly once when the audio leaves the bar:
 *   'ended'   — finished naturally
 *   'stopped' — halted via the manager (bar's stop button / another claim)
 *   'error'   — play() failed
 * `cleanup` runs on every exit path (revoke object URLs etc.).
 */
const playTrackedAudioElement = (a, { label, peaksBlob, cleanup, onDone } = {}) => {
  let finished = false;
  const finish = (reason) => {
    if (finished) return;
    finished = true;
    try {
      cleanup?.();
    } catch {
      /* cleanup must not break playback teardown */
    }
    try {
      onDone?.(reason);
    } catch {
      /* consumer callbacks must not break the manager */
    }
  };
  const session = claimTrackedPlayback({
    source: 'output',
    label,
    stop: () => {
      try {
        a.pause();
      } catch {
        /* already stopped */
      }
      finish('stopped');
    },
    seek: (t) => {
      try {
        const d = Number.isFinite(a.duration) ? a.duration : Infinity;
        a.currentTime = Math.max(0, Math.min(t, d));
      } catch {
        /* not seekable yet */
      }
    },
    pause: () => {
      try {
        a.pause();
      } catch {
        /* noop */
      }
    },
    resume: () => {
      a.play().catch(() => {});
    },
  });
  const pushTime = () =>
    session.update({
      currentTime: a.currentTime || 0,
      duration: Number.isFinite(a.duration) ? a.duration : 0,
    });
  // Optional chaining: unit-test doubles of Audio() may omit the event API.
  a.addEventListener?.('timeupdate', pushTime);
  a.addEventListener?.('durationchange', pushTime);
  a.addEventListener?.('loadedmetadata', pushTime);
  a.addEventListener?.('play', () => session.update({ paused: false }));
  a.addEventListener?.('pause', () => session.update({ paused: true }));
  a.addEventListener?.('ended', () => {
    session.release();
    finish('ended');
  });
  if (peaksBlob) {
    decodePeaksFromBlob(peaksBlob).then((peaks) => {
      if (peaks) session.update({ peaks });
    });
  }
  return { session, finish };
};

export const playBlobAudio = async (blob, meta = {}) => {
    const url = URL.createObjectURL(blob);
    const a = new Audio(url);
    const { session, finish } = playTrackedAudioElement(a, {
      label: meta.label,
      peaksBlob: blob,
      cleanup: () => URL.revokeObjectURL(url),
      onDone: meta.onDone,
    });
    a.play().catch((e) => {
      session.release();
      finish('error');
      console.error('playBlobAudio play error:', e);
    });
};

// ── Notification ping ─────────────────────────────────────────────────

let _pingCtx = null;
export const playPing = () => {
  try {
    if (!_pingCtx) _pingCtx = new (window.AudioContext || window.webkitAudioContext)();
    const ctx = _pingCtx;
    if (ctx.state === 'suspended') ctx.resume();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = 'sine';
    osc.frequency.setValueAtTime(600, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(900, ctx.currentTime + 0.08);
    osc.frequency.exponentialRampToValueAtTime(1200, ctx.currentTime + 0.15);
    gain.gain.setValueAtTime(0, ctx.currentTime);
    gain.gain.linearRampToValueAtTime(0.18, ctx.currentTime + 0.03);
    gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.25);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.25);
  } catch (e) {}
};

// Re-export for convenience
