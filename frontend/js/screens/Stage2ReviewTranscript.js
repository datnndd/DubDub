/**
 * Stage 2: Review Transcript Studio
 * OCR Inspector & Teleprompter Deck for speech validation and slide diffing.
 */

import { renderVideoPlayer } from '../components/VideoPlayer.js';
import { renderWaveformScrubber } from '../components/WaveformScrubber.js';

export function renderStage2ReviewTranscript(state) {
  const seg2 = state.segments.find(s => s.id === 2);

  return `
    <div class="flex-1 min-h-0 w-full p-2.5 flex flex-col gap-2.5 overflow-hidden">
      <!-- TOP HALF: BROADCAST MONITOR & OCR INSPECTOR (52% Height) -->
      <section class="h-[52%] min-h-0 w-full grid grid-cols-12 gap-2.5">
        <!-- LEFT: SYNCHRONIZED VIDEO PLAYER WITH OCR BOUNDING BOX (7 cols) -->
        <div class="col-span-12 xl:col-span-7 h-full flex flex-col min-h-0">
          ${renderVideoPlayer(state, {
            title: "Synchronized Video Player",
            showOcrBox: true,
            subtitleVariant: "dual"
          })}
          ${renderWaveformScrubber(state)}
        </div>

        <!-- RIGHT: OCR SLIDE DIFF INSPECTOR PANEL (5 cols) -->
        <div class="col-span-12 xl:col-span-5 h-full bg-white rounded-xl border border-[#E7E4DC] shadow-xs flex flex-col min-h-0 overflow-hidden">
          <!-- Inspector Header -->
          <div class="h-8 px-3 border-b border-[#E7E4DC] bg-[#FAF9F6] flex items-center justify-between flex-shrink-0">
            <div class="flex items-center gap-2">
              <span class="material-symbols-outlined text-[#8D4B00] text-sm">find_replace</span>
              <span class="text-xs font-bold text-stone-900">OCR Slide Diff Inspector</span>
              <span class="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold bg-amber-100 text-amber-900 border border-amber-200">
                1 Pending Diff
              </span>
            </div>
            <span class="text-[9px] font-mono text-stone-500">Keyframe 01:26.500</span>
          </div>

          <!-- Diff Inspection Body -->
          <div class="flex-1 min-h-0 overflow-y-auto p-3 flex flex-col justify-between space-y-2.5">
            <div class="space-y-2">
              <div class="p-2 rounded-lg bg-amber-50/70 border border-amber-200">
                <div class="flex items-center justify-between mb-1">
                  <span class="text-[9px] font-bold text-[#8D4B00] uppercase tracking-wider flex items-center gap-1">
                    <span class="material-symbols-outlined text-xs">warning</span>
                    Conflict Detected at Segment #02
                  </span>
                  <span class="text-[9px] font-mono text-stone-500">Confidence Score: 94.8%</span>
                </div>
                <p class="text-[11px] text-stone-700 leading-snug">
                  ASR spoken audio differs significantly from the text rendered on the keynote presentation slide.
                </p>
              </div>

              <!-- Side-by-side comparison boxes -->
              <div class="space-y-1.5">
                <!-- Option A: ASR Audio Speech -->
                <div class="p-2.5 rounded-lg border border-stone-200 bg-stone-50">
                  <div class="flex items-center justify-between text-[10px] text-stone-500 mb-1">
                    <span class="font-bold flex items-center gap-1">
                      <span class="material-symbols-outlined text-xs text-primary">hearing</span>
                      Spoken Audio (ASR Whisper Large-v3)
                    </span>
                    <span class="font-mono text-stone-400">Audio Track</span>
                  </div>
                  <p class="text-xs text-stone-900 font-medium bg-white p-2 rounded border border-stone-200">
                    “${seg2.sourceText}”
                  </p>
                </div>

                <!-- Option B: On-Screen Slide OCR -->
                <div class="p-2.5 rounded-lg border-2 border-[#8D4B00] bg-amber-50/40">
                  <div class="flex items-center justify-between text-[10px] text-[#8D4B00] mb-1">
                    <span class="font-bold flex items-center gap-1">
                      <span class="material-symbols-outlined text-xs">document_scanner</span>
                      On-Screen Slide (Visual OCR Box #01)
                    </span>
                    <span class="font-mono bg-amber-200/80 text-amber-900 px-1 rounded text-[9px] font-bold">99.4% Match</span>
                  </div>
                  <p class="text-xs text-amber-950 font-bold bg-white p-2 rounded border border-amber-200 shadow-2xs">
                    “${seg2.ocrSlideText}”
                  </p>
                </div>
              </div>
            </div>

            <!-- Resolution Actions -->
            <div class="pt-2 border-t border-stone-200 flex flex-col gap-1.5">
              <span class="text-[9px] font-bold text-stone-400 uppercase tracking-wider">Choose Resolution for Dubbing</span>
              <div class="grid grid-cols-2 gap-1.5">
                <button 
                  class="py-1.5 px-2 rounded-lg bg-white hover:bg-stone-50 text-stone-700 font-semibold text-xs border border-stone-300 shadow-2xs transition-colors"
                  onclick="window.dubDubStore.resolveOcrDiff(2, false); alert('Retained Spoken Audio (ASR)');">
                  Keep Spoken (ASR)
                </button>
                <button 
                  class="py-1.5 px-2 rounded-lg bg-[#8D4B00] hover:bg-[#743d00] text-white font-bold text-xs shadow-2xs transition-colors flex items-center justify-center gap-1"
                  onclick="window.dubDubStore.resolveOcrDiff(2, true); alert('Adopted Slide OCR Text!');">
                  <span class="material-symbols-outlined text-xs">check</span>
                  Use Slide OCR
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- BOTTOM HALF: EXPANSIVE MASTER TELEPROMPTER & SCRIPT FEED (48% Height) -->
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
            <label class="flex items-center gap-1.5 text-[10px] text-stone-500 cursor-pointer">
              <input checked class="rounded border-stone-300 text-[#8D4B00] focus:ring-0 w-3 h-3 bg-white" type="checkbox" />
              <span>Auto-scroll with playhead</span>
            </label>
          </div>

          <!-- Search & Filter Bar -->
          <div class="flex items-center gap-2">
            <div class="relative w-52">
              <span class="material-symbols-outlined absolute left-2 top-1.5 text-stone-400 text-xs">search</span>
              <input 
                class="w-full bg-white pl-6 pr-2 py-0.5 rounded-lg text-xs text-stone-800 placeholder:text-stone-400 focus:outline-none focus:ring-1 focus:ring-primary border border-stone-200 leading-tight" 
                placeholder="Search dialogue phrase..." 
                type="text" 
              />
            </div>
            <select class="bg-white text-[10px] text-stone-700 font-medium py-0.5 px-2 rounded-lg border border-stone-200 focus:outline-none cursor-pointer">
              <option>All Speakers (2)</option>
              <option>Alex Carter</option>
              <option>Elena Rostova</option>
            </select>
            <button class="p-1 rounded-md bg-stone-100 hover:bg-stone-200 text-stone-600 border border-stone-200/80 transition-colors" title="Find & Replace">
              <span class="material-symbols-outlined text-xs">find_replace</span>
            </button>
            <button class="p-1 rounded-md bg-stone-100 hover:bg-stone-200 text-stone-600 border border-stone-200/80 transition-colors" title="Re-align timing">
              <span class="material-symbols-outlined text-xs">sync</span>
            </button>
          </div>
        </div>

        <!-- Teleprompter Dialogue Rows -->
        <div class="flex-1 min-h-0 overflow-y-auto p-2.5 space-y-2">
          ${state.segments.map(seg => {
            const isActive = seg.id === 2;
            const hasConflict = seg.hasOcrDiff && !seg.ocrResolved;

            return `
              <div class="p-2.5 rounded-xl border ${isActive ? 'border-2 border-[#8D4B00] bg-amber-50/40 active-teleprompter-card' : 'border-stone-200 bg-white hover:border-amber-200'} shadow-2xs flex flex-col md:flex-row md:items-center gap-3 relative transition-all">
                <!-- Left Metadata & Speaker Badge -->
                <div class="flex md:flex-col justify-between md:justify-center items-start gap-1 w-full md:w-44 flex-shrink-0">
                  <div class="flex items-center gap-1.5">
                    <span class="px-1.5 py-0.2 rounded bg-[#8D4B00] text-white font-mono text-[10px] font-bold">#0${seg.id}</span>
                    <div class="flex items-center gap-1 px-1.5 py-0.2 rounded-full bg-amber-100/80 text-amber-900 border border-amber-200 text-[10px] font-bold">
                      <span class="w-3 h-3 rounded-full bg-[#8D4B00] text-white text-[8px] flex items-center justify-center">${seg.speakerCode}</span>
                      <span>${seg.speakerName}</span>
                    </div>
                  </div>
                  <span class="font-mono text-[10px] text-stone-500">${seg.startTime} ➔ ${seg.endTime}</span>
                  <div class="flex items-center gap-1">
                    <span class="px-1.5 py-0.2 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 text-[9px] font-bold">
                      ${seg.cps} CPS • ${seg.cpsStatus}
                    </span>
                    ${hasConflict ? `
                      <span class="px-1.5 py-0.2 rounded bg-amber-100 text-amber-800 border border-amber-300 text-[9px] font-bold flex items-center gap-0.5">
                        <span class="material-symbols-outlined text-[10px]">warning</span> OCR Diff
                      </span>
                    ` : ''}
                  </div>
                </div>

                <!-- Center Source Dialogue Text with in-place edit -->
                <div class="flex-1 min-w-0">
                  <div class="text-[9px] font-mono text-stone-400 mb-0.5">ORIGINAL SOURCE (EN)</div>
                  <input 
                    class="w-full bg-white border border-stone-200 focus:border-[#8D4B00] focus:ring-0 rounded p-1.5 text-xs text-stone-800 font-medium"
                    value="${seg.sourceText}"
                    onchange="window.dubDubStore.updateSegment(${seg.id}, 'sourceText', this.value)"
                  />
                </div>

                <!-- Right Quick Play / Tools -->
                <div class="flex items-center gap-1.5 flex-shrink-0">
                  <button 
                    class="p-1.5 rounded-lg bg-stone-100 hover:bg-amber-100 text-stone-700 hover:text-[#8D4B00] transition-colors border border-stone-200" 
                    title="Audition Cue"
                    onclick="window.dubDubStore.setPlaybackTime(${seg.startSec})">
                    <span class="material-symbols-outlined text-sm">play_circle</span>
                  </button>
                  <button class="p-1.5 rounded-lg bg-stone-100 hover:bg-stone-200 text-stone-600 transition-colors border border-stone-200" title="Split Segment">
                    <span class="material-symbols-outlined text-sm">content_cut</span>
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
