/**
 * Stage 2: Review Transcript Studio
 * OCR Inspector & Teleprompter Deck for speech validation and slide diffing.
 */

import { renderVideoPlayer } from '../components/VideoPlayer.js';
import { renderTranslationConfig } from '../components/TranslationConfig.js';

export function renderStage2ReviewTranscript(state) {
  const escapeHtml = value => String(value || '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);

  const distinctSpeakers = new Set(state.segments.map(s => s.speakerName || s.speakerId || s.speakerLabel || s.speaker).filter(Boolean)).size;
  const diarizationEnabled = Boolean(state.engines && state.engines.speakerDiarization);
  const multiSpeaker = diarizationEnabled && distinctSpeakers > 1;

  const speakerColorClasses = {
    amber: 'bg-amber-100 text-amber-900 border-amber-300',
    secondary: 'bg-indigo-100 text-indigo-900 border-indigo-300',
    emerald: 'bg-emerald-100 text-emerald-900 border-emerald-300',
    rose: 'bg-rose-100 text-rose-900 border-rose-300',
    purple: 'bg-purple-100 text-purple-900 border-purple-300',
  };

  const speakerDotBg = {
    amber: 'bg-[#8D4B00]',
    secondary: 'bg-indigo-600',
    emerald: 'bg-emerald-600',
    rose: 'bg-rose-600',
    purple: 'bg-purple-600',
  };

  return `
    <div class="flex-1 min-h-0 w-full p-2 flex flex-col gap-2 overflow-hidden">
      <!-- TOP SECTION: MAXIMIZED BROADCAST MONITOR & COMPACT TRANSLATION PANEL (62% Height) -->
      <section class="h-[62%] min-h-0 w-full grid grid-cols-12 gap-2">
        <!-- LEFT: MAXIMIZED SYNCHRONIZED VIDEO PLAYER (9 cols) -->
        <div class="col-span-12 lg:col-span-8 xl:col-span-9 h-full flex flex-col min-h-0">
          ${renderVideoPlayer(state, {
    title: "Synchronized Video Player",
    showOcrBox: false,
    subtitleVariant: "none"
  })}
        </div>

        <!-- RIGHT: COMPACT LLM TRANSLATION CONFIGURATION PANEL (3 cols) -->
        ${renderTranslationConfig(state, {
    containerClass: "col-span-12 lg:col-span-4 xl:col-span-3 h-full",
    title: "LLM Translation",
    headerHeight: "h-7.5",
    badge: "Reasoning"
  })}
      </section>

      <!-- BOTTOM SECTION: COMPACT TELEPROMPTER & SCRIPT FEED (38% Height) -->
      <section class="h-[38%] min-h-0 w-full bg-white rounded-xl border border-[#E7E4DC] shadow-xs flex flex-col overflow-hidden">
        <!-- Teleprompter Stream Header Bar -->
        <div class="h-7.5 px-3 border-b border-[#E7E4DC] bg-[#FAF9F6] flex items-center justify-between flex-shrink-0">
          <div class="flex items-center gap-2.5">
            <div class="flex items-center gap-1.5">
              <span class="material-symbols-outlined text-[#8D4B00] text-sm">subtitles</span>
              <h3 class="text-xs font-bold text-stone-900">Transcript Cues</h3>
              <span class="px-1.5 py-0.2 rounded-full bg-amber-50 text-amber-900 border border-amber-200 font-mono text-[9px] font-bold">
                ${state.segments.length} Dialogue Segments
              </span>
              ${state.backend && state.backend.asrDuration ? `
                <span class="px-1.5 py-0.2 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 font-mono text-[9px] font-bold flex items-center gap-1" title="Measured Deepgram / ASR execution duration">
                  <span class="material-symbols-outlined text-xs text-emerald-600">bolt</span>
                  <span>ASR: ${state.backend.asrDuration}s</span>
                </span>
              ` : ''}
            </div>
            <div class="h-3 w-px bg-stone-200"></div>
            <span class="text-[9px] text-stone-500 hidden md:inline">
              Click to audition • Edit text inline • Use Split to divide at playhead/cursor • Targeted OCR replacement
            </span>
          </div>

          <div class="flex items-center gap-2">
            <span class="text-[9px] font-mono font-medium text-stone-500">
              Playhead: <span class="font-bold text-stone-800">${state.playback.formattedTime}</span>
            </span>
          </div>
        </div>

        <!-- Teleprompter Dialogue Rows -->
        <div class="flex-1 min-h-0 overflow-y-auto p-2 space-y-1.5">
          ${state.segments.map(seg => {
    const isActive = String(seg.id) === String(state.activeSegmentId);
    const activeSeg = isActive;
    const hasConflict = seg.hasOcrDiff && !seg.ocrResolved;
    const colorClass = speakerColorClasses[seg.speakerColor] || 'bg-amber-100 text-amber-900 border-amber-300';
    const dotBg = speakerDotBg[seg.speakerColor] || 'bg-[#8D4B00]';
    const safeId = escapeHtml(JSON.stringify(seg.id));

    return `
              <div 
                data-segment-card="${escapeHtml(seg.id)}"
                class="px-2.5 py-1.5 rounded-lg border ${isActive ? 'border-2 border-[#8D4B00] bg-amber-50/50 shadow-xs' : 'border-stone-200 bg-white hover:border-amber-300 hover:bg-stone-50/40'} shadow-2xs flex flex-col md:flex-row md:items-center gap-2 relative transition-all cursor-pointer"
                onclick="window.dubDubStore.seekAndPlay(${seg.startSec}, ${safeId})">
                
                <!-- Left Metadata & Speaker Badge -->
                <div class="flex md:flex-col justify-between md:justify-center items-start gap-0.5 w-full md:w-36 flex-shrink-0">
                  <div class="flex items-center gap-1">
                    <span class="px-1 py-0.2 rounded bg-[#8D4B00] text-white font-mono text-[9px] font-bold">#${String(seg.id).padStart(2, '0')}</span>
                    
                    ${multiSpeaker ? `
                      <div class="flex items-center gap-1 px-1.5 py-0.2 rounded-full ${colorClass} border text-[9px] font-bold shadow-2xs">
                        <span class="w-2.5 h-2.5 rounded-full ${dotBg} text-white text-[7px] flex items-center justify-center">${escapeHtml(seg.speakerCode || 'S')}</span>
                        <span>${escapeHtml(seg.speakerName || seg.speakerLabel || seg.speaker || 'Speaker')}</span>
                      </div>
                    ` : `
                      <div class="flex items-center gap-1 px-1.5 py-0.2 rounded-full bg-stone-100 text-stone-700 border border-stone-200 text-[9px] font-bold shadow-2xs">
                        <span class="w-2.5 h-2.5 rounded-full bg-stone-400 text-white text-[7px] flex items-center justify-center">S1</span>
                        <span>Speaker 1</span>
                      </div>
                    `}
                    <span data-cps-badge class="px-1 py-0.2 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 text-[8px] font-bold font-mono">
                      ${seg.cps || 12} CPS
                    </span>
                    ${hasConflict ? `
                      <span class="px-1 py-0.2 rounded bg-amber-100 text-amber-800 border border-amber-300 text-[8px] font-bold flex items-center gap-0.5">
                        <span class="material-symbols-outlined text-[9px]">warning</span> Diff
                      </span>
                    ` : ''}
                  </div>

                  <span class="font-mono text-[9px] text-stone-500 font-semibold">${seg.startTime || '00:00.000'} ➔ ${seg.endTime || '00:00.000'}</span>
                </div>

                <!-- Center Source Dialogue Text with in-place edit -->
                <div class="flex-1 min-w-0" onclick="event.stopPropagation()">
                  <textarea
                    rows="1"
                    data-segment-input="${escapeHtml(seg.id)}"
                    class="w-full bg-white border border-stone-200 focus:border-[#8D4B00] focus:ring-1 focus:ring-[#8D4B00] rounded-md py-1 px-2 text-xs text-stone-900 font-medium transition-colors resize-none leading-normal min-h-[28px]"
                    placeholder="Enter transcript segment..."
                    onclick="event.stopPropagation(); window.dubDubStore.setActiveEditor(${safeId}, this.selectionStart)"
                    onfocus="window.dubDubStore.setActiveEditor(${safeId}, this.selectionStart)"
                    onblur="setTimeout(() => { if (window.dubDubStore.activeEditor && String(window.dubDubStore.activeEditor.segmentId) === String(${safeId})) window.dubDubStore.clearActiveEditor(${safeId}); }, 250); window.dubDubStore.updateSegmentText(${safeId}, this.value, true);"
                    onkeyup="window.dubDubStore.setActiveEditor(${safeId}, this.selectionStart)"
                    onselect="window.dubDubStore.setActiveEditor(${safeId}, this.selectionStart)"
                    oninput="window.dubDubStore.updateSegmentText(${safeId}, this.value)"
                    onchange="window.dubDubStore.updateSegmentText(${safeId}, this.value, true)"
                  >${escapeHtml(seg.sourceText !== undefined && seg.sourceText !== null ? seg.sourceText : (seg.text || ''))}</textarea>
                </div>

                <!-- Right Actions: Audition, Split Segment, Replace with OCR -->
                <div class="flex items-center gap-1 flex-shrink-0" onclick="event.stopPropagation()">
                  <button 
                    class="p-1 rounded-md bg-stone-100 hover:bg-amber-100 text-stone-700 hover:text-[#8D4B00] transition-colors border border-stone-200" 
                    title="Audition Cue"
                    onclick="window.dubDubStore.seekAndPlay(${seg.startSec}, ${safeId})">
                    <span class="material-symbols-outlined text-sm">play_circle</span>
                  </button>

                  <button 
                    class="px-2 py-1 rounded-md bg-stone-100 hover:bg-stone-200 text-stone-700 transition-colors border border-stone-200 text-[10px] font-semibold flex items-center gap-1"
                    title="Split Segment at current playhead or text cursor"
                    onmousedown="window.dubDubStore.captureEditorBeforeSplit(${safeId})"
                    onclick="window.dubDubStore.splitSegmentCard(${safeId})">
                    <span class="material-symbols-outlined text-xs">content_cut</span>
                    <span>Split Segment</span>
                  </button>

                  <button 
                    class="px-2 py-1 rounded-md bg-amber-50 hover:bg-amber-100 text-[#8D4B00] transition-colors border border-amber-200 text-[10px] font-semibold flex items-center gap-1"
                    title="Replace with PaddleOCR subtitle from video frames"
                    onclick="window.dubDubStore.openOcrCrop(${safeId})">
                    <span class="material-symbols-outlined text-xs">document_scanner</span>
                    <span>Replace with OCR</span>
                  </button>
                </div>
              </div>
            `;
  }).join('')}
        </div>
      </section>

      <!-- Full-Screen Translation Loading Modal Overlay -->
      ${renderTranslationModal(state, escapeHtml)}
    </div>
  `;
}

function renderTranslationModal(state, escapeHtml) {
  if (!state.translationModal || !state.translationModal.active) return '';
  const modal = state.translationModal;
  const opt = state.backend && state.backend.options;
  const selectedProvider = (opt && opt.translationProviders && opt.translationProviders.find(
    item => item.translateType === Number(state.backend?.config?.translateType)
  )) || (opt && opt.translationProviders && opt.translationProviders[0]) || { label: 'LLM Translation', model: '' };
  const providerLabel = selectedProvider.label || 'Translation';
  const targetLangName = state.languages?.target?.name || (state.languages?.target?.code || '').toUpperCase() || 'Target';
  const progressPct = Math.min(100, Math.max(0, Math.round(Number(modal.progress) || 0)));

  return `
    <!-- Full-Screen Translation Loading Modal -->
    <div data-translation-modal class="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div class="bg-white w-full max-w-md rounded-2xl border border-stone-200 shadow-2xl overflow-hidden flex flex-col p-6 items-center text-center">
        <!-- Animated Spinner -->
        <div class="w-16 h-16 rounded-full bg-amber-50 border-2 border-amber-200 flex items-center justify-center mb-4 text-[#8D4B00]">
          <span data-translation-spinner class="material-symbols-outlined text-3xl animate-spin">progress_activity</span>
        </div>

        <!-- Title & Subtitle -->
        <h3 class="text-base font-bold text-stone-900 mb-1">Translating Transcript</h3>
        <p class="text-xs text-stone-500 mb-3">Translating dialogue segments into <span class="font-bold text-stone-700">${escapeHtml(targetLangName)}</span></p>

        <!-- Provider / Model Badge -->
        <div class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-stone-100 border border-stone-200 text-stone-700 text-[11px] font-mono font-medium mb-4">
          <span class="material-symbols-outlined text-xs text-[#8D4B00]">psychology</span>
          <span>${escapeHtml(providerLabel)}</span>
          ${selectedProvider.model ? `<span class="text-stone-400">•</span><span class="text-stone-600">${escapeHtml(selectedProvider.model)}</span>` : ''}
        </div>

        <!-- Progress Bar -->
        <div class="w-full bg-stone-100 rounded-full h-2 mb-2 overflow-hidden border border-stone-200">
          <div class="bg-[#8D4B00] h-full transition-all duration-300 rounded-full" style="width: ${progressPct}%"></div>
        </div>

        <!-- Progress Feedback -->
        <div data-translation-progress class="flex items-center justify-between w-full text-[11px] text-stone-500 font-medium mb-5 px-0.5">
          <span class="truncate max-w-[260px]">${escapeHtml(modal.message || 'Translating segments…')}</span>
          <span class="font-mono font-bold text-stone-700 ml-2">${progressPct}%</span>
        </div>

        <!-- Cancel Action Button -->
        <button 
          type="button"
          data-action="cancel-translation"
          data-translation-cancel
          onclick="window.dubDubStore.cancelTranslation()"
          class="px-4 py-2 rounded-xl bg-stone-100 hover:bg-stone-200 active:bg-stone-300 text-stone-700 font-semibold text-xs border border-stone-200 transition-colors flex items-center gap-1.5 cursor-pointer">
          <span class="material-symbols-outlined text-sm text-stone-500">close</span>
          <span>Cancel Translation</span>
        </button>
      </div>
    </div>
  `;
}

