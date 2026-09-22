import { StateCreator } from 'zustand';

export function formatTimecode(seconds: number): string {
  if (isNaN(seconds) || seconds < 0) return '00:00.000';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 1000);
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}.${String(ms).padStart(3, '0')}`;
}

export interface PlaybackSlice {
  playback: {
    currentTime: number;
    formattedTime: string;
    duration: number;
    isPlaying: boolean;
    playbackSpeed: number;
    audioChannel: 'orig' | 'dub';
  };
  seek: (seconds: number) => void;
  setPlaying: (playing: boolean) => void;
  setPlaybackSpeed: (speed: number) => void;
  setAudioChannel: (channel: 'orig' | 'dub') => void;
  updatePlaybackTime: (currentTime: number, duration?: number) => void;
}

export const createPlaybackSlice: StateCreator<any, [], [], PlaybackSlice> = (set, get) => ({
  playback: {
    currentTime: 0,
    formattedTime: '00:00.000',
    duration: 0,
    isPlaying: false,
    playbackSpeed: 1.0,
    audioChannel: 'dub',
  },

  seek: (seconds: number) => {
    const dur = get().playback.duration || get().project?.durationSec || 0;
    const clamped = Math.max(0, dur > 0 ? Math.min(seconds, dur) : seconds);
    set((state: any) => ({
      playback: {
        ...state.playback,
        currentTime: clamped,
        formattedTime: formatTimecode(clamped),
      },
    }));

    // Find and activate segment corresponding to clamped time
    const segments = get().segments || [];
    const active = segments.find((s: any) => clamped >= s.startSec && clamped <= s.endSec);
    if (active && active.id !== get().activeSegmentId) {
      set({ activeSegmentId: active.id });
    }
  },

  setPlaying: (isPlaying: boolean) => {
    set((state: any) => ({
      playback: { ...state.playback, isPlaying },
    }));
  },

  setPlaybackSpeed: (playbackSpeed: number) => {
    set((state: any) => ({
      playback: { ...state.playback, playbackSpeed },
    }));
  },

  setAudioChannel: (audioChannel: 'orig' | 'dub') => {
    set((state: any) => ({
      playback: { ...state.playback, audioChannel },
    }));
  },

  updatePlaybackTime: (currentTime: number, duration?: number) => {
    set((state: any) => {
      const dur = duration !== undefined ? duration : state.playback.duration;
      return {
        playback: {
          ...state.playback,
          currentTime,
          formattedTime: formatTimecode(currentTime),
          duration: dur,
        },
      };
    });

    const segments = get().segments || [];
    const active = segments.find((s: any) => currentTime >= s.startSec && currentTime <= s.endSec);
    if (active && active.id !== get().activeSegmentId) {
      set({ activeSegmentId: active.id });
    }
  },
});
