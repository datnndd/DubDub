import React from 'react';
import { useDubDubStore } from '../store';
import { VideoPlayer } from '../components/VideoPlayer';
import { Volume2, Play, Sliders, Mic, RefreshCw } from 'lucide-react';

export const Stage3VoiceDubbing: React.FC = () => {
  const segments = useDubDubStore((s) => s.segments);
  const speakers = useDubDubStore((s) => s.getDistinctSpeakers());
  const speakerVoiceMap = useDubDubStore((s) => s.speakerVoiceMap);
  const segmentVoiceOverrides = useDubDubStore((s) => s.segmentVoiceOverrides);
  const voices = useDubDubStore((s) => s.voices);
  const tuning = useDubDubStore((s) => s.tuning);
  const setSpeakerVoice = useDubDubStore((s) => s.setSpeakerVoice);
  const setSegmentVoiceOverride = useDubDubStore((s) => s.setSegmentVoiceOverride);
  const clearSegmentVoiceOverride = useDubDubStore((s) => s.clearSegmentVoiceOverride);
  const updateTuning = useDubDubStore((s) => s.updateTuning);
  const updateSegmentText = useDubDubStore((s) => s.updateSegmentText);

  return (
    <div className="flex-1 min-h-0 w-full p-2.5 grid grid-cols-12 gap-2.5 overflow-hidden">
      {/* LEFT: Synchronized Video Preview (6 cols) */}
      <div className="col-span-12 lg:col-span-6 xl:col-span-6 h-full min-h-0 overflow-hidden">
        <VideoPlayer title="Neural Voice Synthesis Deck" subtitleVariant="dual" showAudioSwitcher={true} />
      </div>

      {/* RIGHT: Speaker Voice Matrix & Per-Segment Overrides (6 cols) */}
      <div className="col-span-12 lg:col-span-6 xl:col-span-6 h-full bg-white rounded-xl border border-[#E7E4DC] shadow-xs flex flex-col min-h-0 overflow-hidden">
        {/* Header Strip */}
        <div className="h-10 px-3 border-b border-[#E7E4DC] flex items-center justify-between bg-[#FAF9F6] shrink-0">
          <div className="flex items-center gap-2">
            <Mic className="w-4 h-4 text-[#8D4B00]" />
            <span className="font-bold text-xs text-stone-900">Multi-Speaker Voice Matrix</span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-[#8D4B00]">
              {speakers.length} Speakers
            </span>
          </div>
        </div>

        {/* Scrollable Body */}
        <div className="flex-1 overflow-y-auto p-3 space-y-4">
          {/* Speaker Cards */}
          <div className="space-y-2.5">
            <h4 className="text-[11px] font-bold uppercase tracking-wider text-stone-400">Speaker Voice Cast</h4>
            {speakers.map((spk) => {
              const currentVoice = speakerVoiceMap[spk.id] || (voices[0]?.id ?? 'default');
              return (
                <div
                  key={spk.id}
                  className="p-3 rounded-xl border border-stone-200 bg-stone-50/50 flex items-center justify-between gap-3"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="w-8 h-8 rounded-full bg-[#8D4B00] text-white flex items-center justify-center font-bold text-xs shrink-0">
                      {spk.code || spk.id.slice(0, 2).toUpperCase()}
                    </div>
                    <div className="min-w-0">
                      <div className="font-bold text-xs text-stone-900 truncate">{spk.name}</div>
                      <div className="text-[10px] text-stone-500 truncate">{spk.role || 'Primary Speaker'}</div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <select
                      value={currentVoice}
                      onChange={(e) => setSpeakerVoice(spk.id, e.target.value)}
                      className="text-xs font-semibold p-1.5 bg-white rounded-lg border border-stone-200 focus:border-amber-400"
                    >
                      {voices.length > 0 ? (
                        voices.map((v) => (
                          <option key={v.id} value={v.id}>
                            {v.name}
                          </option>
                        ))
                      ) : (
                        <option value="default">Default Neural Voice</option>
                      )}
                    </select>
                  </div>
                </div>
              );
            })}
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
                  <span className="font-mono font-bold">{tuning.pace.toFixed(2)}x</span>
                </div>
                <input
                  type="range"
                  min="0.75"
                  max="1.5"
                  step="0.05"
                  value={tuning.pace}
                  onChange={(e) => updateTuning('pace', parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>

              <div>
                <div className="flex items-center justify-between text-[10px] text-stone-600 mb-1">
                  <span>Timbre Warmth</span>
                  <span className="font-mono font-bold">{tuning.timbreWarmth}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={tuning.timbreWarmth}
                  onChange={(e) => updateTuning('timbreWarmth', parseInt(e.target.value))}
                  className="w-full"
                />
              </div>
            </div>
          </div>

          {/* Per-Segment Voice Overrides */}
          <div className="space-y-2.5">
            <h4 className="text-[11px] font-bold uppercase tracking-wider text-stone-400">
              Dialogue Cue Overrides
            </h4>
            {segments.map((seg) => {
              const hasOverride = Boolean(segmentVoiceOverrides[seg.id]);
              const activeVoice = segmentVoiceOverrides[seg.id] || speakerVoiceMap[seg.speakerId] || 'Default';

              return (
                <div key={seg.id} className="p-2.5 rounded-lg border border-stone-200 bg-white space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5">
                      <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-stone-100 text-stone-700">
                        #{seg.id}
                      </span>
                      <span className="font-mono text-[10px] text-stone-500">{seg.startTime}</span>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <select
                        value={activeVoice}
                        onChange={(e) => setSegmentVoiceOverride(seg.id, e.target.value)}
                        className="text-[11px] p-1 bg-stone-50 rounded border border-stone-200"
                      >
                        {voices.map((v) => (
                          <option key={v.id} value={v.id}>
                            {v.name}
                          </option>
                        ))}
                      </select>

                      {hasOverride && (
                        <button
                          onClick={() => clearSegmentVoiceOverride(seg.id)}
                          className="p-1 rounded hover:bg-stone-100 text-stone-400 hover:text-stone-700"
                          title="Reset to Speaker Default"
                        >
                          <RefreshCw className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                  </div>

                  <textarea
                    data-segment-input={`stage3-${seg.id}`}
                    value={seg.targetText || seg.sourceText}
                    onChange={(e) => updateSegmentText(seg.id, e.target.value, true)}
                    rows={1}
                    className="w-full text-xs p-1.5 bg-stone-50 rounded border border-stone-200"
                  />
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
