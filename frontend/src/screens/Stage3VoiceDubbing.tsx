import React, { useState, useRef, useEffect, useMemo } from 'react';
import { useDubDubStore } from '../store';
import { VideoPlayer } from '../components/VideoPlayer';
import { VoiceSelector } from '../components/VoiceSelector';
import {
  Volume2,
  Play,
  Pause,
  Sliders,
  Mic,
  RefreshCw,
  Plus,
  ArrowRight,
  Sparkles,
  Loader2,
  Users,
} from 'lucide-react';
import { previewTTS } from '../api/voices';
import type { Segment } from '../types/segment';

const TTS_PROVIDERS = [
  { id: 0, name: 'ElevenLabs' },
  { id: 1, name: 'OmniVoice' },
  { id: 2, name: 'VieNeu-TTS' },
  { id: 3, name: 'Gemini TTS' },
];

const getSpeakerBadgeClasses = (color?: string) => {
  switch (color) {
    case 'secondary':
    case 'purple':
      return 'bg-purple-700 text-white';
    case 'emerald':
    case 'green':
      return 'bg-emerald-700 text-white';
    case 'sky':
    case 'blue':
      return 'bg-sky-700 text-white';
    case 'indigo':
      return 'bg-indigo-700 text-white';
    case 'rose':
    case 'red':
      return 'bg-rose-700 text-white';
    case 'amber':
    default:
      return 'bg-[#8D4B00] text-white';
  }
};

export const Stage3VoiceDubbing: React.FC = () => {
  const segments = useDubDubStore((s) => s.segments);
  const rawSpeakers = useDubDubStore((s) => s.speakers);
  const getDistinctSpeakers = useDubDubStore((s) => s.getDistinctSpeakers);
  const speakerVoiceMap = useDubDubStore((s) => s.speakerVoiceMap);
  const segmentVoiceOverrides = useDubDubStore((s) => s.segmentVoiceOverrides);
  const voices = useDubDubStore((s) => s.voices);
  const tuning = useDubDubStore((s) => s.tuning);
  const backend = useDubDubStore((s) => s.backend);
  const languages = useDubDubStore((s) => s.languages);
  const seek = useDubDubStore((s) => s.seek);
  const seekAndPlay = useDubDubStore((s) => s.seekAndPlay);
  const activeSegmentId = useDubDubStore((s) => s.activeSegmentId);
  const setStep = useDubDubStore((s) => s.setStep);
  const triggerAutosave = useDubDubStore((s) => s.triggerAutosave);
  const setSpeakerVoice = useDubDubStore((s) => s.setSpeakerVoice);
  const setSegmentVoiceOverride = useDubDubStore((s) => s.setSegmentVoiceOverride);
  const clearSegmentVoiceOverride = useDubDubStore((s) => s.clearSegmentVoiceOverride);
  const updateSegmentVoicePreview = useDubDubStore((s) => s.updateSegmentVoicePreview);
  const updateTuning = useDubDubStore((s) => s.updateTuning);
  const updateSegmentText = useDubDubStore((s) => s.updateSegmentText);
  const setCreateVoiceModalOpen = useDubDubStore((s) => s.setCreateVoiceModalOpen);
  const setVoiceManagerDrawerOpen = useDubDubStore((s) => s.setVoiceManagerDrawerOpen);
  const loadVoices = useDubDubStore((s) => s.loadVoices);
  const updateBackendConfig = useDubDubStore((s) => (s as any).updateBackendConfig);

  const [loadingPreviewMap, setLoadingPreviewMap] = useState<Record<number, boolean>>({});
  const [playingSegmentId, setPlayingSegmentId] = useState<number | null>(null);
  const previewAudioRef = useRef<HTMLAudioElement | null>(null);

  const speakers = useMemo(() => {
    return getDistinctSpeakers(segments, rawSpeakers);
  }, [segments, rawSpeakers, getDistinctSpeakers]);

  const currentProvider = Number(backend?.config?.ttsType ?? 2);

  // Ensure voices are loaded for current provider
  useEffect(() => {
    loadVoices();
  }, [currentProvider, loadVoices]);

  // Stop preview audio playback on unmount
  useEffect(() => {
    return () => {
      if (previewAudioRef.current) {
        previewAudioRef.current.pause();
        previewAudioRef.current = null;
      }
    };
  }, []);

  const handleProviderChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newProvider = parseInt(e.target.value, 10);
    if (updateBackendConfig) {
      updateBackendConfig('ttsType', newProvider);
    }
    await loadVoices();
    triggerAutosave();
  };

  const handleTogglePlay = (segmentId: number, audioUrl: string) => {
    if (playingSegmentId === segmentId) {
      if (previewAudioRef.current) {
        previewAudioRef.current.pause();
      }
      setPlayingSegmentId(null);
    } else {
      if (previewAudioRef.current) {
        previewAudioRef.current.pause();
      }
      const audio = new Audio(audioUrl);
      previewAudioRef.current = audio;
      audio.onended = () => setPlayingSegmentId(null);
      audio.onerror = () => setPlayingSegmentId(null);
      audio.play().catch(() => setPlayingSegmentId(null));
      setPlayingSegmentId(segmentId);
    }
  };

  const handleGeneratePreview = async (seg: Segment, activeVoice: string) => {
    setLoadingPreviewMap((prev) => ({ ...prev, [seg.id]: true }));
    try {
      const textToSynthesize = seg.targetText || seg.sourceText || '';
      const res = await previewTTS({
        text: textToSynthesize,
        voice: activeVoice,
        provider: currentProvider,
        language: languages?.target?.code || 'vi',
        speed: tuning?.pace,
        segment_id: seg.id,
        force_refresh: true,
      });

      const audioUrl = res.audio_url || res.preview_url;
      updateSegmentVoicePreview(seg.id, audioUrl, res.id || res.preview_id, activeVoice);
    } catch (err) {
      console.error(`Preview generation failed for segment ${seg.id}:`, err);
    } finally {
      setLoadingPreviewMap((prev) => ({ ...prev, [seg.id]: false }));
    }
  };

  return (
    <div className="flex-1 min-h-0 w-full p-2.5 grid grid-cols-12 gap-2.5 overflow-hidden">
      {/* LEFT: Synchronized Video Preview (6 cols) */}
      <div className="col-span-12 lg:col-span-6 xl:col-span-6 h-full min-h-0 overflow-hidden">
        <VideoPlayer title="Neural Voice Synthesis Deck" subtitleVariant="dual" showAudioSwitcher={true} />
      </div>

      {/* RIGHT: Speaker Voice Matrix & Per-Segment Overrides (6 cols) */}
      <div className="col-span-12 lg:col-span-6 xl:col-span-6 h-full bg-white rounded-xl border border-[#E7E4DC] shadow-xs flex flex-col min-h-0 overflow-hidden">
        {/* Header Strip */}
        <div className="h-11 px-3 border-b border-[#E7E4DC] flex items-center justify-between bg-[#FAF9F6] shrink-0 gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <Mic className="w-4 h-4 text-[#8D4B00] shrink-0" />
            <span className="font-bold text-xs text-stone-900 truncate">Multi-Speaker Voice Matrix</span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-[#8D4B00] shrink-0">
              {speakers.length} Speakers
            </span>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            <button
              data-action="proceed-to-edit-video"
              onClick={() => {
                triggerAutosave();
                setStep(4);
              }}
              className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-[#8D4B00] text-white hover:bg-[#723c00] transition-colors cursor-pointer shadow-2xs"
              title="Proceed to Edit Video (Stage 4)"
            >
              <span>Proceed to Edit Video</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setCreateVoiceModalOpen(true)}
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-semibold bg-white border border-stone-200 text-stone-700 hover:bg-stone-50 hover:border-amber-400 transition-colors cursor-pointer shadow-2xs"
              title="Create New Custom Cloned Voice"
            >
              <Plus className="w-3.5 h-3.5 text-[#8D4B00]" />
              <span>Create Voice</span>
            </button>
            <button
              onClick={() => setVoiceManagerDrawerOpen(true)}
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium text-stone-700 bg-white border border-stone-200 hover:bg-stone-50 hover:border-amber-400 transition-colors cursor-pointer shadow-2xs"
              title="Open Voice Management Library"
            >
              <Sliders className="w-3.5 h-3.5 text-stone-500" />
              <span>Library</span>
            </button>
          </div>
        </div>

        {/* Scrollable Body */}
        <div className="flex-1 overflow-y-auto p-3 space-y-4">
          {/* Upper Voice Casting Console */}
          <div className="space-y-2.5 bg-stone-50/70 p-3 rounded-xl border border-stone-200">
            <div className="flex items-center justify-between gap-2">
              <h4 className="text-[11px] font-bold uppercase tracking-wider text-stone-500">
                Upper Voice Casting Console
              </h4>
              <div className="flex items-center gap-1.5">
                <label className="text-[11px] font-semibold text-stone-600">Provider:</label>
                <select
                  data-action="select-tts-provider"
                  value={currentProvider}
                  onChange={handleProviderChange}
                  className="text-xs bg-white border border-stone-200 rounded px-2 py-1 font-semibold text-stone-800 cursor-pointer focus:outline-none focus:border-[#8D4B00]"
                >
                  {TTS_PROVIDERS.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Speaker Cards */}
            <div className="space-y-2">
              {speakers.map((spk) => {
                const currentVoice = (speakerVoiceMap && speakerVoiceMap[spk.id]) || (voices[0]?.id ?? 'default');
                const badgeClass = getSpeakerBadgeClasses(spk.color);
                return (
                  <div
                    key={spk.id}
                    data-speaker-card={spk.id}
                    className="p-2.5 rounded-lg border border-stone-200 bg-white flex items-center justify-between gap-3 shadow-2xs"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div
                        className={`w-7 h-7 rounded-full flex items-center justify-center font-bold text-xs shrink-0 shadow-2xs ${badgeClass}`}
                      >
                        {spk.code || (spk.id != null ? String(spk.id).slice(0, 2).toUpperCase() : 'SP')}
                      </div>
                      <div className="min-w-0">
                        <div className="font-bold text-xs text-stone-900 truncate">{spk.name}</div>
                        <div className="text-[10px] text-stone-500 truncate">{spk.role || 'Primary Speaker'}</div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0" data-speaker-voice-select={spk.id}>
                      <VoiceSelector
                        value={currentVoice}
                        onChange={(voiceId) => setSpeakerVoice(spk.id, voiceId)}
                        size="md"
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Global Dubbing Tuning Faders */}
          <div className="p-3 rounded-xl border border-stone-200 bg-stone-50/50 space-y-3">
            <div className="flex items-center gap-1.5 font-bold text-xs text-stone-900">
              <Sliders className="w-3.5 h-3.5 text-[#8D4B00]" />
              <span>Voice Synthesis Tuning</span>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="flex items-center justify-between text-[10px] text-stone-600 mb-1">
                  <span>Speech Rate</span>
                  <span className="font-mono font-bold">{(tuning?.pace ?? 1.0).toFixed(2)}x</span>
                </div>
                <input
                  type="range"
                  min="0.75"
                  max="1.5"
                  step="0.05"
                  value={tuning?.pace ?? 1.0}
                  onChange={(e) => updateTuning('pace', parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>

              <div>
                <div className="flex items-center justify-between text-[10px] text-stone-600 mb-1">
                  <span>Timbre Warmth</span>
                  <span className="font-mono font-bold">{tuning?.timbreWarmth ?? 62}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={tuning?.timbreWarmth ?? 62}
                  onChange={(e) => updateTuning('timbreWarmth', parseInt(e.target.value))}
                  className="w-full"
                />
              </div>
            </div>
          </div>

          {/* Per-Segment Dialogue Blocks */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-[11px] font-bold uppercase tracking-wider text-stone-400">
                Dialogue Cue Overrides
              </h4>
              <span className="text-[10px] text-stone-500 font-mono">
                {segments.length} {segments.length === 1 ? 'cue' : 'cues'}
              </span>
            </div>

            {segments.map((seg) => {
              const rawSpkId = seg.speakerId ?? (seg as any).speakerLabel ?? (seg as any).speakerName ?? 'spk_1';
              const segSpkId = String(rawSpkId).trim();
              const matchedSpeaker = speakers.find((s) => s.id === segSpkId || (seg.speakerId != null && s.id === String(seg.speakerId)));
              const spkCode = seg.speakerCode || matchedSpeaker?.code || (segSpkId.length > 1 ? segSpkId.slice(0, 2).toUpperCase() : 'S1');
              const spkName = seg.speakerName || matchedSpeaker?.name || 'Speaker 1';
              const spkColor = seg.speakerColor || matchedSpeaker?.color || 'amber';
              const badgeClass = getSpeakerBadgeClasses(spkColor);

              const hasOverride = Boolean(
                (segmentVoiceOverrides && segmentVoiceOverrides[seg.id]) || seg.voiceOverride
              );
              const activeVoice =
                (segmentVoiceOverrides && segmentVoiceOverrides[seg.id]) ||
                seg.voiceOverride ||
                (speakerVoiceMap && (speakerVoiceMap[segSpkId] || (seg.speakerId != null ? speakerVoiceMap[String(seg.speakerId)] : undefined))) ||
                (voices[0]?.id ?? 'Default');

              const isLoadingPreview = Boolean(loadingPreviewMap[seg.id]);
              const isPlayingThis = playingSegmentId === seg.id;

              return (
                <div
                  key={seg.id}
                  data-segment-card={`stage3-${seg.id}`}
                  onClick={(e) => {
                    const target = e.target as HTMLElement;
                    if (target.closest('button, select, textarea, input, label, a')) return;
                    seekAndPlay(seg.startSec, seg.endSec, seg.id);
                  }}
                  className={`p-3 rounded-xl border transition-all cursor-pointer ${
                    activeSegmentId === seg.id
                      ? 'border-[#8D4B00] bg-amber-50/20 ring-1 ring-[#8D4B00]/20 shadow-xs'
                      : 'border-stone-200 bg-white hover:border-stone-300 shadow-2xs'
                  } space-y-2.5`}
                >
                  {/* Block Header: Speaker Badge, Timestamp, Voice Selector */}
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0 flex-wrap">
                      <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-stone-100 text-stone-700">
                        #{seg.id}
                      </span>

                      {/* Original Speaker Badge with Stage 2 styling */}
                      <span
                        data-speaker-badge={seg.speakerId || segSpkId}
                        className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wide inline-flex items-center gap-1 shadow-2xs ${badgeClass}`}
                      >
                        <span className="opacity-90 font-mono">{spkCode}</span>
                        <span>{spkName}</span>
                      </span>

                      {/* Seekable Timestamp */}
                      <button
                        data-action="seek-segment"
                        onClick={(e) => {
                          e.stopPropagation();
                          seekAndPlay(seg.startSec, seg.endSec, seg.id);
                        }}
                        className="font-mono text-[10px] text-stone-500 font-semibold hover:text-[#8D4B00] transition-colors flex items-center gap-1 cursor-pointer"
                        title="Play video for this dialogue cue"
                      >
                        <Play className="w-2.5 h-2.5 fill-current text-[#8D4B00]" />
                        <span>{seg.startTime}</span>
                        {seg.endTime && <span className="opacity-60">➔ {seg.endTime}</span>}
                      </button>
                    </div>

                    {/* Dual-Level Voice Selector */}
                    <div className="flex items-center gap-1.5 shrink-0">
                      {!hasOverride && (
                        <span className="text-[9px] font-bold text-stone-400 bg-stone-100 px-1.5 py-0.5 rounded uppercase tracking-wide">
                          (Default)
                        </span>
                      )}

                      <VoiceSelector
                        value={activeVoice}
                        onChange={(voiceId) => setSegmentVoiceOverride(seg.id, voiceId)}
                        size="sm"
                      />

                      {hasOverride && (
                        <button
                          data-action="reset-segment-voice"
                          onClick={() => clearSegmentVoiceOverride(seg.id)}
                          className="p-1 rounded hover:bg-stone-100 text-stone-400 hover:text-stone-700 cursor-pointer"
                          title="Reset to Speaker Default"
                        >
                          <RefreshCw className="w-3 h-3" />
                        </button>
                      )}

                      <button
                        data-action="set-speaker-default"
                        onClick={() => {
                          const targetSpkId = matchedSpeaker?.id || seg.speakerId || segSpkId;
                          setSpeakerVoice(targetSpkId, activeVoice);
                          clearSegmentVoiceOverride(seg.id);
                        }}
                        className="p-1 rounded hover:bg-stone-100 text-stone-400 hover:text-[#8D4B00] cursor-pointer"
                        title={`Apply "${activeVoice}" as default for ${spkName}`}
                      >
                        <Users className="w-3 h-3" />
                      </button>
                    </div>
                  </div>

                  {/* Texts: Source Text & Editable Target Dubbing Script */}
                  <div className="space-y-2">
                    <div>
                      <label className="text-[10px] text-stone-400 font-medium block mb-0.5">
                        Source Text
                      </label>
                      <div className="w-full text-xs p-2 rounded-lg bg-stone-50 border border-stone-100 text-stone-600 select-text">
                        {seg.sourceText || seg.text || '—'}
                      </div>
                    </div>

                    <div>
                      <label className="text-[10px] font-semibold text-stone-700 block mb-0.5">
                        Target Dubbing Text
                      </label>
                      <textarea
                        data-segment-input={`stage3-${seg.id}`}
                        value={seg.targetText ?? ''}
                        onChange={(e) => updateSegmentText(seg.id, e.target.value, true)}
                        rows={2}
                        className="w-full text-xs p-2 rounded-lg bg-white border border-stone-200 focus:border-[#8D4B00] focus:ring-1 focus:ring-[#8D4B00] outline-none transition-all"
                        placeholder="Enter translated target script for voice synthesis…"
                      />
                    </div>
                  </div>

                  {/* Voice Preview Controls for each block */}
                  <div className="pt-2 border-t border-stone-100 flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <button
                        data-action="generate-voice-preview"
                        onClick={() => handleGeneratePreview(seg, activeVoice)}
                        disabled={isLoadingPreview}
                        className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-semibold bg-amber-50 text-[#8D4B00] border border-amber-200/80 hover:bg-amber-100 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shadow-2xs"
                        title="Generate voice preview for this text block"
                      >
                        {isLoadingPreview ? (
                          <>
                            <Loader2 className="w-3 h-3 animate-spin" />
                            <span>Generating Preview…</span>
                          </>
                        ) : (
                          <>
                            <Sparkles className="w-3 h-3 text-[#8D4B00]" />
                            <span>{seg.previewAudioUrl && (!seg.previewVoice || seg.previewVoice === activeVoice) ? 'Regenerate Voice Preview' : 'Generate Voice Preview'}</span>
                          </>
                        )}
                      </button>

                      {seg.previewAudioUrl && (
                        <div className="flex items-center gap-1.5 bg-stone-100 px-2 py-0.5 rounded-md border border-stone-200">
                          <button
                            data-action="play-voice-preview"
                            onClick={() => handleTogglePlay(seg.id, seg.previewAudioUrl!)}
                            className="p-1 rounded hover:bg-stone-200 text-stone-700 cursor-pointer"
                            title={isPlayingThis ? 'Pause preview' : 'Play audition preview'}
                          >
                            {isPlayingThis ? (
                              <Pause className="w-3 h-3 fill-current text-[#8D4B00]" />
                            ) : (
                              <Play className="w-3 h-3 fill-current text-[#8D4B00]" />
                            )}
                          </button>
                          <span className="text-[10px] font-mono text-stone-600 font-medium">
                            {seg.previewVoice && seg.previewVoice !== activeVoice ? `Audition (${seg.previewVoice})` : 'Audition'}
                          </span>
                        </div>
                      )}
                    </div>

                    <div className="text-[10px] text-stone-400 font-mono truncate">
                      Voice: <span className="font-semibold text-stone-600">{activeVoice}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
