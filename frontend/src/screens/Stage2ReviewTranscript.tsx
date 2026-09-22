import React from 'react';
import { useDubDubStore } from '../store';
import { VideoPlayer } from '../components/VideoPlayer';
import { Search, Split, Trash2, Merge, Sparkles, Languages, Check, X, Loader2 } from 'lucide-react';

export const Stage2ReviewTranscript: React.FC = () => {
  const segments = useDubDubStore((s) => s.segments);
  const activeSegmentId = useDubDubStore((s) => s.activeSegmentId);
  const setActiveSegmentId = useDubDubStore((s) => s.setActiveSegmentId);
  const searchQuery = useDubDubStore((s) => s.searchQuery);
  const setSearchQuery = useDubDubStore((s) => s.setSearchQuery);
  const updateSegmentText = useDubDubStore((s) => s.updateSegmentText);
  const splitSegment = useDubDubStore((s) => s.splitSegment);
  const deleteSegment = useDubDubStore((s) => s.deleteSegment);
  const mergeWithNextSegment = useDubDubStore((s) => s.mergeWithNextSegment);
  const extractOcrForSegment = useDubDubStore((s) => s.extractOcrForSegment);
  const runBatchTranslation = useDubDubStore((s) => s.runBatchTranslation);
  const translationModal = useDubDubStore((s) => s.translationModal);
  const closeTranslationModal = useDubDubStore((s) => s.closeTranslationModal);

  const filteredSegments = segments.filter((seg) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      seg.sourceText.toLowerCase().includes(q) ||
      seg.targetText.toLowerCase().includes(q) ||
      (seg.speakerName && seg.speakerName.toLowerCase().includes(q))
    );
  });

  return (
    <div className="flex-1 min-h-0 w-full p-2.5 grid grid-cols-12 gap-2.5 overflow-hidden">
      {/* LEFT: Synchronized Video Player (6-7 cols) */}
      <div className="col-span-12 lg:col-span-6 xl:col-span-7 h-full min-h-0 overflow-hidden">
        <VideoPlayer title="Transcript Teleprompter Deck" subtitleVariant="dual" showAudioSwitcher={true} />
      </div>

      {/* RIGHT: Segment Cue Cards (5-6 cols) */}
      <div className="col-span-12 lg:col-span-6 xl:col-span-5 h-full bg-white rounded-xl border border-[#E7E4DC] shadow-xs flex flex-col min-h-0 overflow-hidden">
        {/* Header Strip with Search & Batch Translate */}
        <div className="h-10 px-3 border-b border-[#E7E4DC] flex items-center justify-between bg-[#FAF9F6] shrink-0 gap-2">
          <div className="relative flex-1 max-w-xs">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-stone-400" />
            <input
              type="text"
              placeholder="Search transcript..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-2.5 py-1 text-xs bg-white rounded-md border border-stone-200 focus:outline-none focus:border-amber-400"
            />
          </div>

          <button
            onClick={() => runBatchTranslation()}
            className="px-3 py-1 rounded-md bg-[#8D4B00] hover:bg-[#743D00] text-white text-xs font-bold flex items-center gap-1.5 shadow-2xs cursor-pointer"
          >
            <Languages className="w-3.5 h-3.5" />
            <span>Batch Translate</span>
          </button>
        </div>

        {/* Segment Cards List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-3">
          {filteredSegments.map((seg) => {
            const isActive = seg.id === activeSegmentId;
            return (
              <div
                key={seg.id}
                data-segment-card={seg.id}
                onClick={() => setActiveSegmentId(seg.id)}
                className={`p-3 rounded-xl border transition-all ${
                  isActive
                    ? 'border-[#8D4B00] bg-amber-50/25 ring-1 ring-[#8D4B00]/20 shadow-xs'
                    : 'border-stone-200 hover:border-stone-300 bg-white'
                }`}
              >
                {/* Card Header: Speaker, Timecode, CPS */}
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded-full bg-[#8D4B00] text-white text-[9px] font-bold uppercase tracking-wide">
                      {seg.speakerName || seg.speakerId || 'Speaker 1'}
                    </span>
                    <span className="font-mono text-[10px] text-stone-500 font-semibold">
                      {seg.startTime} ➔ {seg.endTime}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <span
                      data-cps-badge="true"
                      className={`px-1.5 py-0.2 rounded text-[9px] font-bold font-mono border ${
                        seg.cps && seg.cps <= 14.5
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : 'bg-amber-50 text-[#8D4B00] border-amber-200'
                      }`}
                    >
                      {seg.cps || 14} CPS • {seg.cpsStatus || 'Optimal'}
                    </span>

                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        splitSegment(seg.id);
                      }}
                      className="p-1 rounded hover:bg-stone-100 text-stone-500 hover:text-stone-800"
                      title="Split segment"
                    >
                      <Split className="w-3 h-3" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        mergeWithNextSegment(seg.id);
                      }}
                      className="p-1 rounded hover:bg-stone-100 text-stone-500 hover:text-stone-800"
                      title="Merge with next"
                    >
                      <Merge className="w-3 h-3" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteSegment(seg.id);
                      }}
                      className="p-1 rounded hover:bg-rose-50 text-stone-400 hover:text-rose-600"
                      title="Delete segment"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </div>

                {/* Source Textarea */}
                <div className="mb-2">
                  <label className="text-[10px] text-stone-400 font-medium block mb-0.5">Source Text</label>
                  <textarea
                    data-segment-input={seg.id}
                    value={seg.sourceText}
                    onChange={(e) => updateSegmentText(seg.id, e.target.value, false)}
                    rows={2}
                    className="w-full text-xs p-2 rounded-lg bg-stone-50 border border-stone-200 focus:bg-white focus:outline-none focus:border-amber-400"
                  />
                </div>

                {/* Target Translated Text */}
                <div>
                  <div className="flex items-center justify-between mb-0.5">
                    <label className="text-[10px] text-stone-400 font-medium">Translated Text</label>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        extractOcrForSegment(seg.id);
                      }}
                      className="text-[9px] text-[#8D4B00] font-semibold hover:underline flex items-center gap-0.5"
                    >
                      <Sparkles className="w-2.5 h-2.5" />
                      <span>OCR Extract</span>
                    </button>
                  </div>
                  <textarea
                    data-segment-input={`stage2-target-${seg.id}`}
                    value={seg.targetText}
                    onChange={(e) => updateSegmentText(seg.id, e.target.value, true)}
                    rows={2}
                    className="w-full text-xs p-2 rounded-lg bg-amber-50/40 border border-amber-200/60 focus:bg-white focus:outline-none focus:border-amber-400 font-medium text-stone-900"
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Translation Progress Modal */}
      {translationModal.active && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs">
          <div className="w-full max-w-sm bg-white rounded-2xl p-5 shadow-2xl border border-stone-200 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 font-bold text-sm text-stone-900">
                <Languages className="w-4 h-4 text-[#8D4B00]" />
                <span>Batch Translation</span>
              </div>
              <button
                onClick={() => closeTranslationModal()}
                className="w-6 h-6 rounded-full hover:bg-stone-100 flex items-center justify-center text-stone-400 hover:text-stone-700"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-stone-600">{translationModal.message}</p>

            {translationModal.status === 'translating' && (
              <div className="w-full h-1.5 bg-stone-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-[#8D4B00] transition-all duration-300 rounded-full"
                  style={{ width: `${translationModal.progress}%` }}
                />
              </div>
            )}

            <div className="flex justify-end gap-2 mt-2">
              <button
                onClick={() => closeTranslationModal()}
                className="px-3 py-1.5 rounded-lg bg-stone-100 hover:bg-stone-200 text-xs font-semibold text-stone-700"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
