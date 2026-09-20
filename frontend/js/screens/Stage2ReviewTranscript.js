/**
 * Stage 2: Review Transcript Studio
 * OCR Inspector & Teleprompter Deck for speech validation and slide diffing.
 */

import { renderVideoPlayer } from '../components/VideoPlayer.js';
import { renderWaveformScrubber } from '../components/WaveformScrubber.js';
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
    <div class="flex-1 min-h-0 w-full p-2.5 flex flex-col gap-2.5 overflow-hidden">
      <!-- TOP HALF: BROADCAST MONITOR & OCR INSPECTOR (52% Height) -->
      <section class="h-[52%] min-h-0 w-full grid grid-cols-12 gap-2.5">
        <!-- LEFT: SYNCHRONIZED VIDEO PLAYER (7 cols) -->
        <div class="col-span-12 xl:col-span-7 h-full flex flex-col min-h-0">
          ${renderVideoPlayer(state, {
            title: "Synchronized Video Player",
            showOcrBox: false,
            subtitleVariant: "dual"
          })}
          ${renderWaveformScrubber(state)}
        </div>

        <!-- RIGHT: LLM TRANSLATION CONFIGURATION PANEL (5 cols) -->
        ${renderTranslationConfig(state, {
          containerClass: "col-span-12 xl:col-span-5 h-full",
          title: "LLM Translation",
          headerHeight: "h-8",
          badge: "Reasoning"
        })}
      </section>

      <!-- BOTTOM HALF: MASTER TELEPROMPTER & SCRIPT FEED (48% Height) -->
      <section class="h-[48%] min-h-0 w-full bg-white rounded-xl border border-[#E7E4DC] shadow-xs flex flex-col overflow-hidden">
        <!-- Teleprompter Stream Header Bar -->
        <div class="h-9 px-3 border-b border-[#E7E4DC] bg-[#FAF9F6] flex items-center justify-between flex-shrink-0">
          <div class="flex items-center gap-3">
            <div class="flex items-center gap-1.5">
              <span class="material-symbols-outlined text-[#8D4B00] text-base">subtitles</span>
              <h3 class="text-xs font-bold text-stone-900">Transcript Cues</h3>
              <span class="px-1.5 py-0.2 rounded-full bg-amber-50 text-amber-900 border border-amber-200 font-mono text-[10px] font-bold">
                ${state.segments.length} Dialogue Segments
              </span>
            </div>
            <div class="h-3.5 w-px bg-stone-200"></div>
            <span class="text-[10px] text-stone-500">
              Click any card to audition audio • Edit text inline • Use Split to divide at playhead/cursor • Targeted OCR replacement
            </span>
          </div>

          <div class="flex items-center gap-2">
            <span class="text-[10px] font-mono font-medium text-stone-500">
              Playhead: <span class="font-bold text-stone-800">${state.playback.formattedTime}</span>
            </span>
          </div>
        </div>

        <!-- Teleprompter Dialogue Rows -->
        <div class="flex-1 min-h-0 overflow-y-auto p-2.5 space-y-2">
          ${state.segments.map(seg => {
            const isActive = String(seg.id) === String(state.activeSegmentId);
            const hasConflict = seg.hasOcrDiff && !seg.ocrResolved;
            const colorClass = speakerColorClasses[seg.speakerColor] || 'bg-amber-100 text-amber-900 border-amber-300';
            const dotBg = speakerDotBg[seg.speakerColor] || 'bg-[#8D4B00]';
            const safeId = escapeHtml(JSON.stringify(seg.id));

            return `
              <div 
                data-segment-card="${escapeHtml(seg.id)}"
                class="p-2.5 rounded-xl border ${isActive ? 'border-2 border-[#8D4B00] bg-amber-50/50 shadow-xs' : 'border-stone-200 bg-white hover:border-amber-300 hover:bg-stone-50/40'} shadow-2xs flex flex-col md:flex-row md:items-center gap-3 relative transition-all cursor-pointer"
                onclick="window.dubDubStore.seekAndPlay(${seg.startSec}, ${safeId})">
                
                <!-- Left Metadata & Speaker Badge -->
                <div class="flex md:flex-col justify-between md:justify-center items-start gap-1 w-full md:w-48 flex-shrink-0">
                  <div class="flex items-center gap-1.5">
                    <span class="px-1.5 py-0.2 rounded bg-[#8D4B00] text-white font-mono text-[10px] font-bold">#${String(seg.id).padStart(2, '0')}</span>
                    
                    ${multiSpeaker ? `
                      <div class="flex items-center gap-1 px-2 py-0.5 rounded-full ${colorClass} border text-[10px] font-bold shadow-2xs">
                        <span class="w-3 h-3 rounded-full ${dotBg} text-white text-[8px] flex items-center justify-center">${escapeHtml(seg.speakerCode || 'S')}</span>
                        <span>${escapeHtml(seg.speakerName || seg.speakerLabel || seg.speaker || 'Speaker')}</span>
                      </div>
                    ` : `
                      <div class="flex items-center gap-1 px-2 py-0.5 rounded-full bg-stone-100 text-stone-700 border border-stone-200 text-[10px] font-bold shadow-2xs">
                        <span class="w-3 h-3 rounded-full bg-stone-400 text-white text-[8px] flex items-center justify-center">S1</span>
                        <span>Speaker 1</span>
                      </div>
                    `}
                  </div>

                  <span class="font-mono text-[10px] text-stone-600 font-semibold">${seg.startTime || '00:00.000'} ➔ ${seg.endTime || '00:00.000'}</span>
                  
                  <div class="flex items-center gap-1">
                    <span data-cps-badge class="px-1.5 py-0.2 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 text-[9px] font-bold font-mono">
                      ${seg.cps || 12} CPS • ${seg.cpsStatus || 'Optimal'}
                    </span>
                    ${hasConflict ? `
                      <span class="px-1.5 py-0.2 rounded bg-amber-100 text-amber-800 border border-amber-300 text-[9px] font-bold flex items-center gap-0.5">
                        <span class="material-symbols-outlined text-[10px]">warning</span> OCR Diff
                      </span>
                    ` : ''}
                  </div>
                </div>

                <!-- Center Source Dialogue Text with in-place edit -->
                <div class="flex-1 min-w-0" onclick="event.stopPropagation()">
                  <div class="text-[9px] font-mono text-stone-400 mb-0.5">ORIGINAL SOURCE DIALOG</div>
                  <textarea
                    rows="2"
                    data-segment-input="${escapeHtml(seg.id)}"
                    class="w-full bg-white border border-stone-200 focus:border-[#8D4B00] focus:ring-1 focus:ring-[#8D4B00] rounded-lg p-2 text-xs text-stone-900 font-medium transition-colors resize-none leading-relaxed"
                    onclick="event.stopPropagation(); window.dubDubStore.setActiveEditor(${safeId}, this.selectionStart)"
                    onfocus="window.dubDubStore.setActiveEditor(${safeId}, this.selectionStart)"
                    onblur="setTimeout(() => { if (window.dubDubStore.activeEditor &amp;&amp; String(window.dubDubStore.activeEditor.segmentId) === String(${safeId})) window.dubDubStore.clearActiveEditor(${safeId}); }, 250); window.dubDubStore.updateSegmentText(${safeId}, this.value, true);"
                    onkeyup="window.dubDubStore.setActiveEditor(${safeId}, this.selectionStart)"
                    onselect="window.dubDubStore.setActiveEditor(${safeId}, this.selectionStart)"
                    oninput="window.dubDubStore.updateSegmentText(${safeId}, this.value)"
                    onchange="window.dubDubStore.updateSegmentText(${safeId}, this.value, true)"
                  >${escapeHtml(seg.sourceText !== undefined && seg.sourceText !== null ? seg.sourceText : (seg.text || ''))}</textarea>
                </div>

                <!-- Right Actions: Audition, Split Segment, Replace with OCR -->
                <div class="flex items-center gap-1.5 flex-shrink-0" onclick="event.stopPropagation()">
                  <button 
                    class="p-1.5 rounded-lg bg-stone-100 hover:bg-amber-100 text-stone-700 hover:text-[#8D4B00] transition-colors border border-stone-200" 
                    title="Audition Cue"
                    onclick="window.dubDubStore.seekAndPlay(${seg.startSec}, ${safeId})">
                    <span class="material-symbols-outlined text-sm">play_circle</span>
                  </button>

                  <button 
                    class="px-2 py-1.5 rounded-lg bg-stone-100 hover:bg-stone-200 text-stone-700 transition-colors border border-stone-200 text-xs font-semibold flex items-center gap-1"
                    title="Split Segment at current playhead or text cursor"
                    onmousedown="window.dubDubStore.captureEditorBeforeSplit(${safeId})"
                    onclick="window.dubDubStore.splitSegmentCard(${safeId})">
                    <span class="material-symbols-outlined text-xs">content_cut</span>
                    <span class="hidden sm:inline text-[10px]">Split</span>
                  </button>

                  <button 
                    class="px-2 py-1.5 rounded-lg bg-amber-50 hover:bg-amber-100 text-[#8D4B00] transition-colors border border-amber-200 text-xs font-semibold flex items-center gap-1"
                    title="Replace with PaddleOCR subtitle from video frames"
                    onclick="window.dubDubStore.openOcrCrop(${safeId})">
                    <span class="material-symbols-outlined text-xs">document_scanner</span>
                    <span class="hidden sm:inline text-[10px]">Replace with OCR</span>
                  </button>
                </div>
              </div>
            `;
          }).join('')}
        </div>
      </section>
    </div>
  `;
}
