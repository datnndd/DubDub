/**
 * Stage 3: Voice & Dubbing Studio
 * Broadcast Split & Teleprompter Deck for multi-role AI voice casting, timbre tuning, and bilingual script playback.
 */

import { renderVideoPlayer } from '../components/VideoPlayer.js';
import { renderWaveformScrubber } from '../components/WaveformScrubber.js';

export function renderStage3VoiceDubbing(state) {
  const spk1 = state.speakers[0];
  const spk2 = state.speakers[1];
  const l = state.languages;

  return `
    <div class="flex-1 min-h-0 w-full p-2.5 flex flex-col gap-2.5 overflow-hidden">
      <!-- TOP HALF: LIVE BROADCAST COMMAND DECK (52% Height) -->
      <section class="h-[52%] min-h-0 w-full grid grid-cols-12 gap-2.5">
        <!-- LEFT: CINEMATIC DUBBING MONITOR (7 cols) -->
        <div class="col-span-12 xl:col-span-7 h-full flex flex-col min-h-0">
          ${renderVideoPlayer(state, {
            title: "Synchronized Dubbing Player",
            showAudioSwitcher: true,
            subtitleVariant: "dual"
          })}
          ${renderWaveformScrubber(state)}
        </div>

        <!-- RIGHT: HORIZONTAL SYNTHESIS & VOICE CONSOLE (5 cols) -->
        <div class="col-span-12 xl:col-span-5 h-full bg-white rounded-xl border border-[#E7E4DC] shadow-xs flex flex-col min-h-0 overflow-hidden">
          <!-- Console Master Header -->
          <div class="h-8 px-3 border-b border-[#E7E4DC] bg-[#FAF9F6] flex items-center justify-between flex-shrink-0">
            <div class="flex items-center gap-2">
              <span class="material-symbols-outlined text-[#8D4B00] text-sm">tune</span>
              <span class="text-xs font-bold text-stone-900">Synthesis Engine</span>
              <span class="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold bg-amber-100 text-[#8D4B00]">v4.2</span>
            </div>

            <!-- Pill Tabs -->
            <div class="flex items-center p-0.5 bg-stone-100 rounded-lg text-[10px] font-bold">
              <button class="px-2 py-0.5 rounded bg-white text-[#8D4B00] shadow-2xs">Dubbing</button>
              <button class="px-2 py-0.5 rounded text-stone-500 hover:text-stone-800 transition-colors">Voices</button>
              <button class="px-2 py-0.5 rounded text-stone-500 hover:text-stone-800 transition-colors">Glossary</button>
            </div>
          </div>

          <!-- Multi-Channel Mixer Grid -->
          <div class="flex-1 min-h-0 overflow-y-auto p-3 space-y-2.5">
            <!-- Channel 1: Language & Tone Mode -->
            <div class="grid grid-cols-2 gap-2">
              <!-- Language Config -->
              <div class="p-2 rounded-lg bg-stone-50 border border-stone-200 flex flex-col justify-between">
                <span class="text-[9px] font-bold text-stone-400 uppercase tracking-wider block">Language Configuration</span>
                <div class="flex items-center justify-between text-[10px] text-stone-500 mt-1">
                  <span>Source</span>
                  <span class="font-bold text-stone-800">${l.source.name}</span>
                </div>
                <div class="h-px bg-stone-200 my-1"></div>
                <div class="flex items-center justify-between text-[10px]">
                  <span class="text-stone-500">Target</span>
                  <select 
                    class="bg-transparent font-bold text-stone-800 text-[10px] focus:outline-none cursor-pointer max-w-[125px] truncate"
                    onchange="window.dubDubStore.updateTargetLanguage(this.value, this.options[this.selectedIndex].text)">
                    ${state.backend.options.languages.map(item => `
                      <option value="${item.code}" ${l.target.code === item.code ? 'selected' : ''}>${item.name}</option>
                    `).join('')}
                  </select>
                </div>
              </div>

              <!-- Model & Tone Mode -->
              <div class="p-2 rounded-lg bg-stone-50 border border-stone-200 flex flex-col justify-between">
                <span class="text-[9px] font-bold text-stone-400 uppercase tracking-wider block">Model &amp; Tone Mode</span>
                <div class="grid grid-cols-2 gap-1 mt-1">
                  <button class="px-1.5 py-1 rounded text-[10px] font-bold bg-[#8D4B00] text-white shadow-2xs leading-none text-center">Conversational</button>
                  <button class="px-1.5 py-1 rounded text-[10px] font-medium bg-white hover:bg-stone-100 text-stone-700 border border-stone-200/80 leading-none text-center">Formal</button>
                  <button class="px-1.5 py-1 rounded text-[10px] font-medium bg-white hover:bg-stone-100 text-stone-700 border border-stone-200/80 leading-none text-center">Colloquial</button>
                  <button class="px-1.5 py-1 rounded text-[10px] font-medium bg-white hover:bg-stone-100 text-stone-700 border border-stone-200/80 leading-none text-center">Technical</button>
                </div>
              </div>
            </div>

            <!-- Channel 2: Voice Actor Profiles Side-by-Side -->
            <div>
              <span class="text-[9px] font-bold text-stone-400 uppercase tracking-wider block mb-1">Voice Actor Profiles</span>
              <div class="grid grid-cols-2 gap-2">
                <!-- Alex Carter -->
                <div class="p-2 rounded-lg bg-stone-50 border border-stone-200 flex items-center justify-between">
                  <div class="flex items-center gap-2 min-w-0">
                    <span class="w-6 h-6 rounded-full bg-amber-500/15 text-[#8D4B00] font-mono text-[10px] font-bold flex items-center justify-center flex-shrink-0">${spk1.code}</span>
                    <div class="min-w-0">
                      <span class="text-[11px] font-bold text-stone-900 block truncate leading-tight">${spk1.name}</span>
                      <span class="text-[9px] text-stone-500 font-mono block truncate">${spk1.preset} • ${spk1.clarity}</span>
                    </div>
                  </div>
                  <span class="material-symbols-outlined text-xs text-stone-400 cursor-pointer hover:text-stone-700 ml-1">tune</span>
                </div>

                <!-- Elena Rostova -->
                <div class="p-2 rounded-lg bg-stone-50 border border-stone-200 flex items-center justify-between">
                  <div class="flex items-center gap-2 min-w-0">
                    <span class="w-6 h-6 rounded-full bg-orange-500/15 text-[#A13E28] font-mono text-[10px] font-bold flex items-center justify-center flex-shrink-0">${spk2.code}</span>
                    <div class="min-w-0">
                      <span class="text-[11px] font-bold text-stone-900 block truncate leading-tight">${spk2.name}</span>
                      <span class="text-[9px] text-stone-500 font-mono block truncate">${spk2.preset} • ${spk2.clarity}</span>
                    </div>
                  </div>
                  <span class="material-symbols-outlined text-xs text-stone-400 cursor-pointer hover:text-stone-700 ml-1">tune</span>
                </div>
              </div>
            </div>

            <!-- Channel 3: Dual Sliders & Locked Glossary -->
            <div class="grid grid-cols-12 gap-2 pt-1 border-t border-stone-200">
              <!-- Tuning Sliders (7 cols) -->
              <div class="col-span-7 space-y-1.5 pr-1">
                <div>
                  <div class="flex justify-between text-[10px] mb-0.5">
                    <span class="text-stone-600 font-medium">Dubbing Pace (0.8x - 1.2x)</span>
                    <span class="font-mono text-[#8D4B00] font-bold">${state.tuning.pace.toFixed(2)}x Auto-Fit</span>
                  </div>
                  <input 
                    class="w-full accent-[#8D4B00] h-1 bg-stone-200 rounded-lg cursor-pointer" 
                    max="120" 
                    min="80" 
                    type="range" 
                    value="${Math.round(state.tuning.pace * 100)}"
                    oninput="window.dubDubStore.updateTuning('pace', this.value / 100)"
                  />
                </div>
                <div>
                  <div class="flex justify-between text-[10px] mb-0.5">
                    <span class="text-stone-600 font-medium">Timbre Warmth</span>
                    <span class="font-mono text-stone-700 font-bold">+${Math.round((state.tuning.timbreWarmth - 50) / 6)} dB</span>
                  </div>
                  <input 
                    class="w-full accent-amber-700 h-1 bg-stone-200 rounded-lg cursor-pointer" 
                    max="100" 
                    min="0" 
                    type="range" 
                    value="${state.tuning.timbreWarmth}"
                    oninput="window.dubDubStore.updateTuning('timbreWarmth', parseInt(this.value))"
                  />
                </div>
              </div>

              <!-- Locked Terms Strip (5 cols) -->
              <div class="col-span-5 flex flex-col justify-between pl-1 border-l border-stone-200">
                <div class="flex items-center justify-between">
                  <span class="text-[9px] font-bold text-stone-400 uppercase tracking-wider">Locked Terms</span>
                  <button class="text-[9px] font-bold text-[#8D4B00] hover:underline" onclick="alert('Add custom terminology glossary pair')">+ Add</button>
                </div>
                <div class="space-y-1 text-[9px] mt-1">
                  ${state.lockedTerms.map(term => `
                    <div class="flex items-center justify-between px-1.5 py-0.5 rounded bg-stone-50 border border-stone-200">
                      <span class="font-mono text-stone-600 truncate">“${term.source}”</span>
                      <span class="text-stone-400 mx-0.5">➔</span>
                      <span class="font-mono text-[#8D4B00] font-bold truncate">“${term.target}”</span>
                    </div>
                  `).join('')}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- BOTTOM HALF: EXPANSIVE MASTER TELEPROMPTER & SUBTITLE FEED (48% Height) -->
      <section class="h-[48%] min-h-0 w-full bg-white rounded-xl border border-[#E7E4DC] shadow-xs flex flex-col overflow-hidden">
        <!-- Teleprompter Stream Header Bar -->
        <div class="h-9 px-3 border-b border-[#E7E4DC] bg-[#FAF9F6] flex items-center justify-between flex-shrink-0">
          <div class="flex items-center gap-3">
            <div class="flex items-center gap-1.5">
              <span class="material-symbols-outlined text-[#8D4B00] text-base">subtitles</span>
              <h3 class="text-xs font-bold text-stone-900">Subtitles &amp; Dubs</h3>
              <span class="px-1.5 py-0.2 rounded-full bg-amber-50 text-amber-900 border border-amber-200 font-mono text-[10px] font-bold">48 Items</span>
            </div>
            <div class="h-3.5 w-px bg-stone-200"></div>
            <label class="flex items-center gap-1.5 text-[10px] text-stone-500 cursor-pointer">
              <input checked class="rounded border-stone-300 text-[#8D4B00] focus:ring-0 w-3 h-3 bg-white" type="checkbox" />
              <span>Auto-follow playhead</span>
            </label>
          </div>

          <!-- Search, Filter & Quick Action Tools -->
          <div class="flex items-center gap-2">
            <div class="relative w-52">
              <span class="material-symbols-outlined absolute left-2 top-1.5 text-stone-400 text-xs">search</span>
              <input 
                class="w-full bg-white pl-6 pr-2 py-0.5 rounded-lg text-xs text-stone-800 placeholder:text-stone-400 focus:outline-none focus:ring-1 focus:ring-primary border border-stone-200 leading-tight" 
                placeholder="Search phrase..." 
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

        <!-- Wide Horizontal-Flow Teleprompter Ribbon -->
        <div class="flex-1 min-h-0 overflow-y-auto p-2.5 space-y-2">
          ${state.segments.map(seg => {
            const isActive = seg.id === 1;

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
                  <span class="px-1.5 py-0.2 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 text-[9px] font-bold">
                    ${seg.cps} CPS • ${seg.cpsStatus}
                  </span>
                </div>

                <!-- Center Bilingual Dialogue Cards (Side-by-Side or Stacked) -->
                <div class="flex-1 grid grid-cols-1 md:grid-cols-2 gap-2 min-w-0">
                  <!-- Translated Speech (Dubbing Target) -->
                  <div class="p-1.5 rounded-lg bg-white border border-stone-200 shadow-2xs">
                    <div class="flex items-center justify-between text-[9px] font-mono text-stone-400 mb-0.5">
                      <span class="text-[#8D4B00] font-bold">AI DUB (ES)</span>
                      <span>Neural Synth</span>
                    </div>
                    <input 
                      class="w-full bg-transparent border-0 p-0 text-xs text-stone-900 font-bold focus:ring-0"
                      value="${seg.targetText}"
                      onchange="window.dubDubStore.updateSegment(${seg.id}, 'targetText', this.value)"
                    />
                  </div>

                  <!-- Source Reference Audio (Original) -->
                  <div class="p-1.5 rounded-lg bg-stone-50 border border-stone-200/80">
                    <div class="text-[9px] font-mono text-stone-400 mb-0.5">SOURCE SPEECH (EN)</div>
                    <p class="text-xs text-stone-600 truncate font-medium">“${seg.sourceText}”</p>
                  </div>
                </div>

                <!-- Right Inline Voice Selector & Quick Audition -->
                <div class="flex items-center gap-2 flex-shrink-0">
                  <select class="bg-white border border-stone-200 text-[10px] font-bold text-stone-800 rounded-lg px-2 py-1 focus:outline-none">
                    <option selected>${seg.speakerName} (${seg.speakerCode === 'AC' ? 'Warm' : 'Broadcast'})</option>
                    <option>Elena Rostova (Guest)</option>
                    <option>Clone Custom Voice...</option>
                  </select>

                  <button 
                    class="p-1.5 rounded-lg bg-amber-100 hover:bg-amber-200 text-[#8D4B00] transition-colors shadow-2xs" 
                    title="Audition Dubbed Audio"
                    onclick="window.dubDubStore.setPlaybackTime(${seg.startSec})">
                    <span class="material-symbols-outlined text-base">volume_up</span>
                  </button>

                  <button class="p-1.5 rounded-lg bg-stone-100 hover:bg-stone-200 text-stone-600 transition-colors" title="Regenerate Voice">
                    <span class="material-symbols-outlined text-sm">cached</span>
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
