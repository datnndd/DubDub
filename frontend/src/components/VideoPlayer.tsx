import React, { useRef, useEffect } from 'react';
import { useDubDubStore } from '../store';
import { Tv as VideoIcon } from 'lucide-react';

interface VideoPlayerProps {
  title?: string;
  subtitleVariant?: 'capcut' | 'dual' | 'none';
  showAudioSwitcher?: boolean;
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({
  title = 'Synchronized Video Player',
  subtitleVariant = 'capcut',
  showAudioSwitcher = false,
}) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const project = useDubDubStore((s) => s.project);
  const playback = useDubDubStore((s) => s.playback);
  const activeSegmentId = useDubDubStore((s) => s.activeSegmentId);
  const segments = useDubDubStore((s) => s.segments);
  const subtitleStyles = useDubDubStore((s) => s.subtitleStyles);
  const editVideo = useDubDubStore((s) => s.editVideo);
  const currentStep = useDubDubStore((s) => s.currentStep);
  const updatePlaybackTime = useDubDubStore((s) => s.updatePlaybackTime);
  const setAudioChannel = useDubDubStore((s) => s.setAudioChannel);

  const currentSegment = segments.find((s) => s.id === activeSegmentId) || segments[0];
  const previewUrl = project.previewUrl || '';

  // Synchronize audio mix and volume
  useEffect(() => {
    if (!videoRef.current) return;
    if (currentStep === 4 && editVideo?.audioMix) {
      const origVol = Number(editVideo.audioMix.original) || 0;
      videoRef.current.volume = Math.max(0, Math.min(1, origVol / 100));
      videoRef.current.muted = origVol === 0;
    }
  }, [currentStep, editVideo?.audioMix]);

  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    updatePlaybackTime(videoRef.current.currentTime, videoRef.current.duration);
  };

  // Subtitle dynamic styles for CapCut canvas
  const capcutStyle: React.CSSProperties = {
    fontFamily: subtitleStyles.fontFamily || 'Arial',
    fontSize: `${subtitleStyles.fontSize || 22}px`,
    color: subtitleStyles.color || '#FFFFFF',
    WebkitTextStroke: `${subtitleStyles.outlineWidth || 2}px ${subtitleStyles.outlineColor || '#000000'}`,
    textShadow: `${subtitleStyles.shadowSize || 2}px ${subtitleStyles.shadowSize || 2}px 0px ${
      subtitleStyles.shadowColor || 'rgba(0,0,0,.75)'
    }`,
  };

  return (
    <div className="h-full w-full bg-white rounded-xl border border-[#E7E4DC] shadow-xs flex flex-col min-h-0 overflow-hidden">
      {/* Player Header Strip */}
      <div className="h-7.5 px-3 border-b border-[#E7E4DC] flex items-center justify-between bg-[#FAF9F6] shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-[#8D4B00] text-sm font-bold">▶</span>
          <span className="text-xs font-bold text-stone-900">{title}</span>
          <span className="px-1.5 py-0.2 rounded text-[8px] font-mono font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
            {project.resolution} • {project.fps}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {showAudioSwitcher && (
            <div className="flex items-center p-0.5 bg-stone-100 rounded-lg border border-stone-200 text-[10px]">
              <button
                className={`px-2 py-0.5 rounded transition-colors ${
                  playback.audioChannel === 'orig'
                    ? 'font-bold bg-white text-[#8D4B00] shadow-2xs border border-amber-200'
                    : 'text-stone-500 hover:text-stone-800'
                }`}
                onClick={() => setAudioChannel('orig')}
              >
                EN Orig
              </button>
              <button
                className={`px-2 py-0.5 rounded transition-colors ${
                  playback.audioChannel === 'dub'
                    ? 'font-bold bg-white text-[#8D4B00] shadow-2xs border border-amber-200'
                    : 'text-stone-500 hover:text-stone-800'
                }`}
                onClick={() => setAudioChannel('dub')}
              >
                ES Dub ★
              </button>
            </div>
          )}

          <span className="px-2 py-0.5 rounded bg-stone-100 text-stone-700 font-mono text-[10px] border border-stone-200 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 warm-pulse" />
            <span>
              <span data-playhead-timecode>{playback.formattedTime}</span> / {project.duration}
            </span>
          </span>
        </div>
      </div>

      {/* Widescreen Visual Preview Container */}
      <div className="relative flex-1 min-h-0 bg-neutral-950 flex items-center justify-center overflow-hidden group">
        {previewUrl ? (
          <video
            ref={videoRef}
            data-source-preview="true"
            className="w-full h-full object-contain bg-black"
            src={previewUrl}
            controls
            preload="metadata"
            onTimeUpdate={handleTimeUpdate}
            onLoadedMetadata={handleTimeUpdate}
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center bg-stone-900 text-stone-400 p-6 text-center">
            <span className="text-3xl mb-2">🎬</span>
            <p className="text-xs font-semibold text-stone-300">No media loaded</p>
            <p className="text-[11px] text-stone-500 mt-1">Upload a video to preview subtitles and playback</p>
          </div>
        )}

        {/* Subtitles Overlay */}
        {subtitleVariant !== 'none' && (
          <div className="absolute inset-x-3 bottom-4 z-20 flex justify-center text-center pointer-events-none">
            {subtitleVariant === 'capcut' ? (
              <div className="w-full max-w-2xl px-4 py-1 flex flex-col items-center">
                <p
                  data-canvas-subtitle="true"
                  className="font-semibold text-center leading-snug tracking-wide select-none"
                  style={capcutStyle}
                >
                  {currentSegment?.targetText || currentSegment?.sourceText || ''}
                </p>
              </div>
            ) : (
              <div className="w-full max-w-xl bg-black/85 backdrop-blur-md px-3.5 py-1.5 rounded-lg border border-amber-500/30 shadow-xl flex flex-col items-center">
                {currentSegment?.speakerName && (
                  <span
                    data-canvas-speaker-badge="true"
                    className="px-2 py-0.5 rounded-full bg-[#8D4B00] text-white text-[9px] font-bold uppercase tracking-wider mb-0.5"
                  >
                    {currentSegment.speakerName}
                  </span>
                )}
                <p data-canvas-subtitle="true" className="text-white font-semibold text-xs leading-snug">
                  {currentSegment?.targetText || currentSegment?.sourceText || ''}
                </p>
                {currentSegment?.sourceText && currentSegment?.targetText && (
                  <p className="text-amber-200/80 text-[10px] font-mono mt-0.5">
                    EN: {currentSegment.sourceText}
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
