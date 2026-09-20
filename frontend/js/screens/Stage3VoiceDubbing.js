/**
 * Stage 3: Voice & Dubbing Studio
 * Broadcast Split & Teleprompter Deck for multi-role AI voice casting, timbre tuning, and bilingual script playback.
 */

import { store } from '../state.js';
import { renderVideoPlayer } from '../components/VideoPlayer.js';

export function renderStage3VoiceDubbing(state) {
  const escapeHtml = value => String(value || '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);

  const distinctSpeakers = store.getDistinctSpeakers();
  const voiceRoles = (state.backend?.options?.voiceRoles && state.backend.options.voiceRoles.length > 0)
    ? state.backend.options.voiceRoles
    : ['No'];
  const ttsProviders = (state.backend?.options?.voices && state.backend.options.voices.length > 0)
    ? state.backend.options.voices
    : [[0, "ElevenLabs"], [1, "OmniVoice(Built-in)"], [2, "VieNeu-TTS"], [3, "Gemini TTS"]];

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
      <!-- TOP HALF: LIVE BROADCAST COMMAND DECK (52% Height) -->
      <section class="h-[52%] min-h-0 w-full grid grid-cols-12 gap-2.5">
        <!-- LEFT: CINEMATIC DUBBING MONITOR (7 cols) -->
        <div class="col-span-12 xl:col-span-7 h-full flex flex-col min-h-0">
          ${renderVideoPlayer(state, {
            title: "Synchronized Dubbing Player",
            showAudioSwitcher: true,
            subtitleVariant: "dual"
          })}
        </div>

        <!-- RIGHT: HORIZONTAL SYNTHESIS & VOICE CONSOLE (5 cols) -->
        <div class="col-span-12 xl:col-span-5 h-full bg-white rounded-xl border border-[#E7E4DC] shadow-xs flex flex-col min-h-0 overflow-hidden">
          <!-- Console Master Header -->
          <div class="h-8 px-3 border-b border-[#E7E4DC] bg-[#FAF9F6] flex items-center justify-between flex-shrink-0">
            <div class="flex items-center gap-2">
              <span class="material-symbols-outlined text-[#8D4B00] text-sm">record_voice_over</span>
              <span class="text-xs font-bold text-stone-900">Voice Casting Console</span>
              <span class="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold bg-amber-100 text-[#8D4B00]">Stage 3</span>
            </div>

            <div class="flex items-center gap-1">
              <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-stone-100 text-stone-600">
                ${distinctSpeakers.length} ${distinctSpeakers.length === 1 ? 'Speaker' : 'Speakers'}
              </span>
            </div>
          </div>

          <!-- Multi-Channel Mixer Grid -->
          <div class="flex-1 min-h-0 overflow-y-auto p-3 space-y-2.5">
            <!-- Channel 1: TTS Provider & Target Language -->
            <div class="grid grid-cols-2 gap-2">
              <!-- TTS Provider Selection -->
              <div class="p-2 rounded-lg bg-stone-50 border border-stone-200 flex flex-col justify-between">
                <span class="text-[9px] font-bold text-stone-500 uppercase tracking-wider block">TTS Provider</span>
                <select
                  data-action="select-tts-provider"
                  class="w-full mt-1 bg-white border border-stone-200 text-stone-800 text-xs font-bold rounded-lg px-2 py-1.5 focus:outline-none focus:border-[#8D4B00] cursor-pointer"
                  onchange="window.dubDubStore.updateBackendConfig('ttsType', Number(this.value))">
                  ${ttsProviders.map(([typeId, label]) => `
                    <option value="${typeId}" ${Number(state.backend?.config?.ttsType) === Number(typeId) ? 'selected' : ''}>
                      ${escapeHtml(label)}
                    </option>
                  `).join('')}
                </select>
              </div>

              <!-- Target Language -->
              <div class="p-2 rounded-lg bg-stone-50 border border-stone-200 flex flex-col justify-between">
                <span class="text-[9px] font-bold text-stone-500 uppercase tracking-wider block">Target Language</span>
                <select 
                  class="w-full mt-1 bg-white border border-stone-200 font-bold text-stone-800 text-xs rounded-lg px-2 py-1.5 focus:outline-none focus:border-[#8D4B00] cursor-pointer"
                  onchange="window.dubDubStore.updateTargetLanguage(this.value, this.options[this.selectedIndex].text)">
                  ${(state.backend?.options?.languages || []).map(item => `
                    <option value="${item.code}" ${state.languages?.target?.code === item.code ? 'selected' : ''}>${escapeHtml(item.name)}</option>
                  `).join('')}
                </select>
              </div>
            </div>

            <!-- Channel 2: Global Speaker-to-Voice Mapping Matrix -->
            <div class="space-y-1.5">
              <div class="flex items-center justify-between">
                <span class="text-[9px] font-bold text-stone-500 uppercase tracking-wider">Dynamic Speaker Matrix</span>
                <span class="text-[9px] font-mono text-stone-400 font-medium">Assigned Voices</span>
              </div>
              <div class="space-y-1.5">
                ${distinctSpeakers.map(speaker => {
                  const assignedVoice = (state.speakerVoiceMap && state.speakerVoiceMap[speaker.speakerId])
                    || state.backend?.config?.voiceRole
                    || (voiceRoles && voiceRoles[0])
                    || 'No';
                  const dotBg = speakerDotBg[speaker.speakerColor] || 'bg-[#8D4B00]';
                  return `
                    <div class="p-2 rounded-lg bg-stone-50 border border-stone-200 flex items-center justify-between gap-2">
                      <div class="flex items-center gap-2 min-w-[120px] flex-shrink-0">
                        <span class="w-6 h-6 rounded-full text-white font-mono text-[10px] font-bold flex items-center justify-center flex-shrink-0 ${dotBg}">
                          ${escapeHtml(speaker.speakerCode || 'S1')}
                        </span>
                        <div class="min-w-0">
                          <span class="text-[11px] font-bold text-stone-900 block truncate leading-tight">${escapeHtml(speaker.speakerName || 'Speaker 1')}</span>
                          <span class="text-[9px] text-stone-500 font-mono block truncate">${escapeHtml(speaker.speakerId)}</span>
                        </div>
                      </div>
                      <select
                        data-speaker-voice-select="${escapeHtml(speaker.speakerId)}"
                        class="bg-white border border-stone-200 text-stone-800 text-xs font-bold rounded-lg px-2 py-1 focus:outline-none focus:border-[#8D4B00] cursor-pointer flex-1"
                        onchange="window.dubDubStore.updateSpeakerVoice('${escapeHtml(speaker.speakerId)}', this.value)">
                        ${voiceRoles.map(v => `
                          <option value="${escapeHtml(v)}" ${v === assignedVoice ? 'selected' : ''}>
                            ${escapeHtml(v)}
                          </option>
                        `).join('')}
                      </select>
                    </div>
                  `;
                }).join('')}
              </div>
            </div>

            <!-- Channel 3: Timbre & Ducking Controls -->
            <div class="grid grid-cols-2 gap-2 pt-2 border-t border-stone-200">
              <div>
                <div class="flex justify-between text-[10px] mb-0.5">
                  <span class="text-stone-600 font-medium">Dubbing Pace</span>
                  <span class="font-mono text-[#8D4B00] font-bold">${(state.tuning?.pace || 1.0).toFixed(2)}x</span>
                </div>
                <input 
                  class="w-full accent-[#8D4B00] h-1 bg-stone-200 rounded-lg cursor-pointer" 
                  max="120" 
                  min="80" 
                  type="range" 
                  value="${Math.round((state.tuning?.pace || 1.0) * 100)}"
                  oninput="window.dubDubStore.updateTuning('pace', this.value / 100)"
                />
              </div>
              <div>
                <div class="flex justify-between text-[10px] mb-0.5">
                  <span class="text-stone-600 font-medium">Timbre Warmth</span>
                  <span class="font-mono text-stone-700 font-bold">+${Math.round(((state.tuning?.timbreWarmth || 50) - 50) / 6)} dB</span>
                </div>
                <input 
                  class="w-full accent-amber-700 h-1 bg-stone-200 rounded-lg cursor-pointer" 
                  max="100" 
                  min="0" 
                  type="range" 
                  value="${state.tuning?.timbreWarmth || 50}"
                  oninput="window.dubDubStore.updateTuning('timbreWarmth', parseInt(this.value))"
                />
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
              <span class="px-1.5 py-0.2 rounded-full bg-amber-50 text-amber-900 border border-amber-200 font-mono text-[10px] font-bold">
                ${state.segments.length} Dialogue Segments
              </span>
            </div>
            <div class="h-3.5 w-px bg-stone-200"></div>
            <span class="text-[10px] text-stone-500">
              Click dialog block to audition • Edit translated text inline • Override voice per block
            </span>
          </div>

          <!-- Timecode Telemetry -->
          <div class="flex items-center gap-2">
            <span class="text-[10px] font-mono font-medium text-stone-500">
              Playhead: <span class="font-bold text-stone-800">${state.playback.formattedTime}</span>
            </span>
          </div>
        </div>

        <!-- Wide Horizontal-Flow Teleprompter Ribbon -->
        <div class="flex-1 min-h-0 overflow-y-auto p-2.5 space-y-2">
          ${state.segments.map(seg => {
            const isActive = String(seg.id) === String(state.activeSegmentId);
            const safeId = escapeHtml(JSON.stringify(seg.id));
            const colorClass = speakerColorClasses[seg.speakerColor] || 'bg-amber-100 text-amber-900 border-amber-300';
            const dotBg = speakerDotBg[seg.speakerColor] || 'bg-[#8D4B00]';

            const globalSpeakerVoice = (state.speakerVoiceMap && state.speakerVoiceMap[seg.speakerId])
              || state.backend?.config?.voiceRole
              || (voiceRoles && voiceRoles[0])
              || 'default';
            const hasOverride = seg.voiceOverride != null;
            const activeVoice = store.getResolvedVoice(seg);

            const startTimeFormatted = store.formatTime(seg.startSec);
            const endTimeFormatted = store.formatTime(seg.endSec);

            return `
              <div 
                data-segment-card="${escapeHtml(seg.id)}"
                data-action="seek-segment"
                data-segment-id="${escapeHtml(seg.id)}"
                class="p-2.5 rounded-xl border ${isActive ? 'border-2 border-[#8D4B00] bg-amber-50/50 shadow-xs' : 'border-stone-200 bg-white hover:border-amber-300 hover:bg-stone-50/40'} shadow-2xs flex flex-col md:flex-row md:items-center gap-3 relative transition-all cursor-pointer"
                onclick="window.dubDubStore.seekAndPlay(${seg.startSec}, ${safeId})">
                
                <!-- Left Metadata & Speaker Badge -->
                <div class="flex md:flex-col justify-between md:justify-center items-start gap-1 w-full md:w-44 flex-shrink-0">
                  <div class="flex items-center gap-1.5">
                    <span class="px-1.5 py-0.2 rounded bg-[#8D4B00] text-white font-mono text-[10px] font-bold">#0${escapeHtml(seg.id)}</span>
                    <div class="flex items-center gap-1 px-1.5 py-0.2 rounded-full border text-[10px] font-bold ${colorClass}">
                      <span class="w-3 h-3 rounded-full text-white text-[8px] font-mono flex items-center justify-center ${dotBg}">${escapeHtml(seg.speakerCode || 'S1')}</span>
                      <span>${escapeHtml(seg.speakerName || 'Speaker 1')}</span>
                    </div>
                  </div>
                  <span class="font-mono text-[10px] text-stone-500 font-medium">${startTimeFormatted} ➔ ${endTimeFormatted}</span>
                  <span class="px-1.5 py-0.2 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 text-[9px] font-bold">
                    ${seg.cps || '14.2'} CPS • ${seg.cpsStatus || 'Optimal'}
                  </span>
                </div>

                <!-- Center Bilingual Dialogue Cards -->
                <div class="flex-1 grid grid-cols-1 md:grid-cols-2 gap-2 min-w-0">
                  <!-- Translated Speech (Dubbing Target) -->
                  <div class="p-2 rounded-lg bg-white border border-stone-200 shadow-2xs">
                    <div class="flex items-center justify-between text-[9px] font-mono text-stone-400 mb-1">
                      <span class="text-[#8D4B00] font-bold">AI DUB (${escapeHtml((state.languages?.target?.code || 'ES').toUpperCase())})</span>
                      <span>Target Text</span>
                    </div>
                    <textarea 
                      rows="2"
                      data-segment-input="stage3-${escapeHtml(seg.id)}"
                      class="w-full bg-white border border-stone-200 focus:border-[#8D4B00] focus:ring-1 focus:ring-[#8D4B00] rounded-lg p-1.5 text-xs text-stone-900 font-medium resize-none leading-relaxed"
                      onclick="event.stopPropagation()"
                      onfocus="window.dubDubStore.setActiveEditor(${safeId}, this.selectionStart)"
                      onblur="setTimeout(() => { if (window.dubDubStore.activeEditor && String(window.dubDubStore.activeEditor.segmentId) === String(${safeId})) window.dubDubStore.clearActiveEditor(${safeId}); }, 250); window.dubDubStore.updateSegmentTargetText(${safeId}, this.value, true);"
                      oninput="window.dubDubStore.updateSegmentTargetText(${safeId}, this.value)"
                      onchange="window.dubDubStore.updateSegmentTargetText(${safeId}, this.value, true)"
                    >${escapeHtml(seg.targetText || '')}</textarea>
                  </div>

                  <!-- Source Reference Audio (Original) -->
                  <div class="p-2 rounded-lg bg-stone-50 border border-stone-200/80 flex flex-col justify-between">
                    <div class="text-[9px] font-mono text-stone-400 mb-1">SOURCE SPEECH (${escapeHtml((state.languages?.source?.code || 'EN').toUpperCase())})</div>
                    <p class="text-xs text-stone-600 line-clamp-2 font-medium">“${escapeHtml(seg.sourceText || '')}”</p>
                    <div class="text-[9px] text-stone-400 font-mono mt-1">Reference Audio</div>
                  </div>
                </div>

                <!-- Right Inline Voice Selector & Actions -->
                <div class="flex items-center gap-1.5 flex-shrink-0">
                  <div class="flex flex-col gap-1 items-end">
                    <select 
                      data-segment-voice-select="${escapeHtml(seg.id)}"
                      class="bg-white border ${hasOverride ? 'border-[#8D4B00] ring-1 ring-[#8D4B00] text-[#8D4B00]' : 'border-stone-200 text-stone-800'} text-[10px] font-bold rounded-lg px-2 py-1.5 focus:outline-none cursor-pointer max-w-[160px] truncate"
                      onclick="event.stopPropagation()"
                      onchange="window.dubDubStore.setSegmentVoiceOverride(${safeId}, this.value)">
                      ${voiceRoles.map(v => `
                        <option value="${escapeHtml(v)}" ${v === activeVoice ? 'selected' : ''}>
                          ${escapeHtml(v)}${v === globalSpeakerVoice ? ' (Default)' : ''}
                        </option>
                      `).join('')}
                    </select>

                    ${hasOverride ? `
                      <button 
                        type="button"
                        data-action="reset-segment-voice"
                        data-segment-id="${escapeHtml(seg.id)}"
                        class="px-2 py-0.5 rounded bg-amber-50 hover:bg-amber-100 text-[#8D4B00] border border-amber-200 text-[9px] font-bold flex items-center gap-0.5 shadow-2xs transition-colors"
                        title="Reset to default voice (${escapeHtml(globalSpeakerVoice)})"
                        onclick="event.stopPropagation(); window.dubDubStore.clearSegmentVoiceOverride(${safeId})">
                        <span class="material-symbols-outlined text-[10px]">restart_alt</span>
                        <span>Reset</span>
                      </button>
                    ` : ''}
                  </div>

                  <button 
                    type="button"
                    data-action="seek-segment"
                    data-segment-id="${escapeHtml(seg.id)}"
                    class="p-1.5 rounded-lg bg-amber-100 hover:bg-amber-200 text-[#8D4B00] transition-colors shadow-2xs" 
                    title="Audition Dubbed Audio"
                    onclick="event.stopPropagation(); window.dubDubStore.seekAndPlay(${seg.startSec}, ${safeId})">
                    <span class="material-symbols-outlined text-base">volume_up</span>
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
