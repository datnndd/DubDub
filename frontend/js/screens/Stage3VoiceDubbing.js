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

  const segments = Array.isArray(state?.segments) ? state.segments : [];
  const safeState = state?.segments ? state : { ...state, segments };

  const distinctSpeakers = (store && typeof store.getDistinctSpeakers === 'function')
    ? store.getDistinctSpeakers()
    : [{ speakerId: 'spk_1', speakerName: 'Speaker 1', speakerCode: 'S1', speakerColor: 'amber' }];

  const voiceRoles = (state?.backend?.options?.voiceRoles && state.backend.options.voiceRoles.length > 0)
    ? state.backend.options.voiceRoles
    : ['No'];
  const ttsProviders = (state?.backend?.options?.voices && state.backend.options.voices.length > 0)
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
      <!-- UPPER DECK: Video Screen (Left) + Voice Console (Right) -->
      <section class="flex-1 min-h-0 w-full grid grid-cols-12 gap-2.5 overflow-hidden">
        <!-- LEFT: SYNCHRONIZED DUBBING PLAYER (7-8 cols) -->
        <div class="col-span-12 lg:col-span-7 xl:col-span-8 h-full flex flex-col min-h-0">
          ${renderVideoPlayer(safeState, {
            title: "Synchronized Dubbing Player",
            showAudioSwitcher: true,
            subtitleVariant: "dual"
          })}
        </div>

        <!-- RIGHT: COMPACT SYNTHESIS & VOICE CASTING CONSOLE (4-5 cols) -->
        <div class="col-span-12 lg:col-span-5 xl:col-span-4 h-full bg-white rounded-xl border border-[#E7E4DC] shadow-xs flex flex-col min-h-0 overflow-hidden">
          <!-- Console Master Header -->
          <div class="h-7.5 px-3 border-b border-[#E7E4DC] bg-[#FAF9F6] flex items-center justify-between flex-shrink-0">
            <div class="flex items-center gap-1.5">
              <span class="material-symbols-outlined text-[#8D4B00] text-sm">record_voice_over</span>
              <h3 class="text-xs font-bold text-stone-900">Voice Casting</h3>
            </div>

            <div class="flex items-center gap-1">
              <span class="px-1.5 py-0.2 rounded text-[9px] font-bold bg-stone-100 text-stone-600">
                ${distinctSpeakers.length} ${distinctSpeakers.length === 1 ? 'Speaker' : 'Speakers'}
              </span>
            </div>
          </div>

          <!-- Multi-Channel Mixer Body -->
          <div class="flex-1 min-h-0 overflow-y-auto p-2 space-y-2">
            <!-- Channel 1: TTS Provider & Target Language -->
            <div class="grid grid-cols-2 gap-1.5">
              <!-- TTS Provider Selection -->
              <div class="p-1.5 rounded-lg bg-stone-50 border border-stone-200 flex flex-col justify-between">
                <span class="text-[8px] font-bold text-stone-500 uppercase tracking-wider block">TTS Provider</span>
                <select
                  data-action="select-tts-provider"
                  class="w-full mt-0.5 bg-white border border-stone-200 text-stone-800 text-xs font-bold rounded-md px-1.5 py-1 focus:outline-none focus:border-[#8D4B00] cursor-pointer"
                  onchange="window.dubDubStore.updateBackendConfig('ttsType', Number(this.value))">
                  ${ttsProviders.map(([typeId, label]) => `
                    <option value="${typeId}" ${Number(state?.backend?.config?.ttsType) === Number(typeId) ? 'selected' : ''}>
                      ${escapeHtml(label)}
                    </option>
                  `).join('')}
                </select>
              </div>

              <!-- Target Language -->
              <div class="p-1.5 rounded-lg bg-stone-50 border border-stone-200 flex flex-col justify-between">
                <span class="text-[8px] font-bold text-stone-500 uppercase tracking-wider block">Target Language</span>
                <select 
                  class="w-full mt-0.5 bg-white border border-stone-200 font-bold text-stone-800 text-xs rounded-md px-1.5 py-1 focus:outline-none focus:border-[#8D4B00] cursor-pointer"
                  onchange="window.dubDubStore.updateTargetLanguage(this.value, this.options[this.selectedIndex].text)">
                  ${(state?.backend?.options?.languages || []).map(item => `
                    <option value="${item.code}" ${state?.languages?.target?.code === item.code ? 'selected' : ''}>${escapeHtml(item.name)}</option>
                  `).join('')}
                </select>
              </div>
            </div>

            <!-- Channel 2: Global Speaker-to-Voice Mapping Matrix -->
            <div class="space-y-1">
              <span class="text-[8px] font-bold text-stone-500 uppercase tracking-wider block">Speaker Voices</span>
              <div class="space-y-1">
                ${distinctSpeakers.map(speaker => {
                  const assignedVoice = (state?.speakerVoiceMap && state.speakerVoiceMap[speaker.speakerId])
                    || state?.backend?.config?.voiceRole
                    || (voiceRoles && voiceRoles[0])
                    || 'No';
                  const dotBg = speakerDotBg[speaker.speakerColor] || 'bg-[#8D4B00]';
                  const safeSpeakerId = escapeHtml(JSON.stringify(speaker.speakerId));
                  return `
                    <div data-speaker-row="${escapeHtml(speaker.speakerId)}" class="p-1.5 rounded-lg bg-stone-50 border border-stone-200 flex items-center justify-between gap-1.5">
                      <div class="flex items-center gap-1.5 min-w-[80px] flex-shrink-0">
                        <span class="w-5 h-5 rounded-full text-white font-mono text-[9px] font-bold flex items-center justify-center flex-shrink-0 ${dotBg}">
                          ${escapeHtml(speaker.speakerCode || 'S1')}
                        </span>
                        <div class="min-w-0">
                          <span class="text-[10px] font-bold text-stone-900 block truncate leading-tight">${escapeHtml(speaker.speakerName || 'Speaker 1')}</span>
                          <span class="text-[8px] text-stone-500 font-mono block truncate">${escapeHtml(speaker.speakerId)}</span>
                        </div>
                      </div>
                      <select
                        data-speaker-voice-select="${escapeHtml(speaker.speakerId)}"
                        class="bg-white border border-stone-200 text-stone-800 text-xs font-bold rounded-md px-1.5 py-1 focus:outline-none focus:border-[#8D4B00] cursor-pointer flex-1 min-w-0"
                        onchange="window.dubDubStore.updateSpeakerVoice(${safeSpeakerId}, this.value)">
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
            <div class="grid grid-cols-2 gap-1.5 pt-1.5 border-t border-stone-200">
              <div>
                <div class="flex justify-between text-[9px] mb-0.5">
                  <span class="text-stone-600 font-medium">Pace</span>
                  <span class="font-mono text-[#8D4B00] font-bold">${(state?.tuning?.pace || 1.0).toFixed(2)}x</span>
                </div>
                <input 
                  class="w-full accent-[#8D4B00] h-1 bg-stone-200 rounded-lg cursor-pointer" 
                  max="120" 
                  min="80" 
                  type="range" 
                  value="${Math.round((state?.tuning?.pace || 1.0) * 100)}"
                  oninput="window.dubDubStore.updateTuning('pace', this.value / 100)"
                />
              </div>
              <div>
                <div class="flex justify-between text-[9px] mb-0.5">
                  <span class="text-stone-600 font-medium">Warmth</span>
                  <span class="font-mono text-stone-700 font-bold">+${Math.round(((state?.tuning?.timbreWarmth || 50) - 50) / 6)} dB</span>
                </div>
                <input 
                  class="w-full accent-[#8D4B00] h-1 bg-stone-200 rounded-lg cursor-pointer" 
                  max="100" 
                  min="0" 
                  type="range" 
                  value="${state?.tuning?.timbreWarmth || 50}"
                  oninput="window.dubDubStore.updateTuning('timbreWarmth', parseInt(this.value))"
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- LOWER DECK: COMPACT TELEPROMPTER & SUBTITLE FEED (Same height as Stage 4 lower deck: 210px) -->
      <section class="h-[210px] flex-shrink-0 w-full bg-white rounded-xl border border-[#E7E4DC] shadow-xs flex flex-col overflow-hidden">
        <!-- Teleprompter Stream Header Bar -->
        <div class="h-7.5 px-3 border-b border-[#E7E4DC] bg-[#FAF9F6] flex items-center justify-between flex-shrink-0">
          <div class="flex items-center gap-2.5">
            <div class="flex items-center gap-1.5">
              <span class="material-symbols-outlined text-[#8D4B00] text-sm">subtitles</span>
              <h3 class="text-xs font-bold text-stone-900">Subtitles &amp; Dubs</h3>
              <span class="px-1.5 py-0.2 rounded-full bg-amber-50 text-amber-900 border border-amber-200 font-mono text-[9px] font-bold">
                ${segments.length} Dialogue Segments
              </span>
            </div>
            <div class="h-3 w-px bg-stone-200"></div>
            <span class="text-[9px] text-stone-500 hidden md:inline">
              Click to audition • Edit target text inline • Override voice per block
            </span>
          </div>

          <!-- Timecode Telemetry -->
          <div class="flex items-center gap-2">
            <span class="text-[9px] font-mono font-medium text-stone-500">
              Playhead: <span class="font-bold text-stone-800">${state?.playback?.formattedTime || '00:00.000'}</span>
            </span>
          </div>
        </div>

        <!-- Teleprompter Dialogue Rows -->
        <div class="flex-1 min-h-0 overflow-y-auto p-2 space-y-1.5">
          ${segments.map(seg => {
            const isActive = String(seg.id) === String(state?.activeSegmentId);
            const safeId = escapeHtml(JSON.stringify(seg.id));
            const colorClass = speakerColorClasses[seg.speakerColor] || 'bg-amber-100 text-amber-900 border-amber-300';
            const dotBg = speakerDotBg[seg.speakerColor] || 'bg-[#8D4B00]';

            const globalSpeakerVoice = (state?.speakerVoiceMap && state.speakerVoiceMap[seg.speakerId])
              || state?.backend?.config?.voiceRole
              || (voiceRoles && voiceRoles[0])
              || 'default';
            const hasOverride = Boolean(seg.voiceOverride);
            const activeVoice = (store && typeof store.getResolvedVoice === 'function') ? store.getResolvedVoice(seg) : 'default';

            const startTimeFormatted = (store && typeof store.formatTime === 'function') ? store.formatTime(seg.startSec) : (seg.startTime || '00:00.000');
            const endTimeFormatted = (store && typeof store.formatTime === 'function') ? store.formatTime(seg.endSec) : (seg.endTime || '00:00.000');

            return `
              <div 
                data-segment-card="${escapeHtml(seg.id)}"
                data-voice-card="${escapeHtml(seg.id)}"
                data-action="seek-segment"
                data-segment-id="${escapeHtml(seg.id)}"
                class="px-2.5 py-1.5 rounded-lg border ${isActive ? 'border-2 border-[#8D4B00] bg-amber-50/50 shadow-xs' : 'border-stone-200 bg-white hover:border-amber-300 hover:bg-stone-50/40'} shadow-2xs flex flex-col md:flex-row md:items-center gap-2 relative transition-all cursor-pointer"
                onclick="window.dubDubStore.seekAndPlay(${seg.startSec || 0}, ${safeId})">
                
                <!-- Left Metadata & Speaker Badge -->
                <div class="flex md:flex-col justify-between md:justify-center items-start gap-0.5 w-full md:w-36 flex-shrink-0">
                  <div class="flex items-center gap-1">
                    <span class="px-1 py-0.2 rounded bg-[#8D4B00] text-white font-mono text-[9px] font-bold">#${String(seg.id).padStart(2, '0')}</span>
                    <div class="flex items-center gap-1 px-1.5 py-0.2 rounded-full border text-[9px] font-bold ${colorClass}">
                      <span class="w-2.5 h-2.5 rounded-full text-white text-[7px] font-mono flex items-center justify-center ${dotBg}">${escapeHtml(seg.speakerCode || 'S1')}</span>
                      <span class="truncate max-w-[70px] sm:max-w-[80px]">${escapeHtml(seg.speakerName || 'Speaker 1')}</span>
                    </div>
                    <span data-cps-badge class="px-1 py-0.2 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 text-[8px] font-bold font-mono">
                      ${seg.targetCps ?? seg.cps ?? '14.2'} CPS
                    </span>
                  </div>
                  <span class="font-mono text-[9px] text-stone-500 font-semibold">${startTimeFormatted} ➔ ${endTimeFormatted}</span>
                </div>

                <!-- Center Bilingual Dialogue Cards -->
                <div class="flex-1 grid grid-cols-1 md:grid-cols-2 gap-1.5 min-w-0">
                  <!-- Translated Speech (Dubbing Target) -->
                  <div class="flex flex-col min-w-0" onclick="event.stopPropagation()">
                    <span class="text-[8px] font-mono text-[#8D4B00] font-bold block uppercase tracking-wider mb-0.5">AI DUB (${escapeHtml((state?.languages?.target?.code || 'ES').toUpperCase())})</span>
                    <textarea 
                      rows="1"
                      data-segment-input="stage3-${escapeHtml(seg.id)}"
                      data-target-input="${escapeHtml(seg.id)}"
                      class="w-full bg-white border border-stone-200 focus:border-[#8D4B00] focus:ring-1 focus:ring-[#8D4B00] rounded-md py-1 px-2 text-xs text-stone-900 font-medium transition-colors resize-none leading-normal min-h-[28px]"
                      placeholder="Enter dubbing target..."
                      onclick="event.stopPropagation(); window.dubDubStore.setActiveEditor(${safeId}, this.selectionStart)"
                      onfocus="window.dubDubStore.setActiveEditor(${safeId}, this.selectionStart)"
                      onblur="setTimeout(() => { if (window.dubDubStore.activeEditor && String(window.dubDubStore.activeEditor.segmentId) === String(${safeId})) window.dubDubStore.clearActiveEditor(${safeId}); }, 250); window.dubDubStore.updateSegmentTargetText(${safeId}, this.value, true);"
                      onkeyup="window.dubDubStore.setActiveEditor(${safeId}, this.selectionStart)"
                      onselect="window.dubDubStore.setActiveEditor(${safeId}, this.selectionStart)"
                      oninput="window.dubDubStore.updateSegmentTargetText(${safeId}, this.value)"
                      onchange="window.dubDubStore.updateSegmentTargetText(${safeId}, this.value, true)"
                    >${escapeHtml(seg.targetText || '')}</textarea>
                  </div>

                  <!-- Source Reference Audio (Original) -->
                  <div class="flex flex-col min-w-0">
                    <span class="text-[8px] font-mono text-stone-400 font-medium block uppercase tracking-wider mb-0.5">SRC (${escapeHtml((state?.languages?.source?.code || 'EN').toUpperCase())})</span>
                    <div class="w-full bg-stone-50 border border-stone-200/80 rounded-md py-1 px-2 text-xs text-stone-600 truncate font-medium min-h-[28px] flex items-center" title="${escapeHtml(seg.sourceText || '')}">
                      “${escapeHtml(seg.sourceText || '')}”
                    </div>
                  </div>
                </div>

                <!-- Right Inline Voice Selector & Actions -->
                <div class="flex items-center gap-1 flex-shrink-0" onclick="event.stopPropagation()">
                  <select 
                    data-segment-voice-select="${escapeHtml(seg.id)}"
                    data-voice-select="${escapeHtml(seg.id)}"
                    class="h-7 bg-white border ${hasOverride ? 'border-[#8D4B00] ring-1 ring-[#8D4B00] text-[#8D4B00]' : 'border-stone-200 text-stone-800'} text-xs font-bold rounded-md px-2 py-0.5 focus:outline-none cursor-pointer max-w-[130px] truncate"
                    title="Select voice role for this segment"
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
                      class="h-7 px-1.5 rounded-md bg-amber-50 hover:bg-amber-100 text-[#8D4B00] border border-amber-200 text-[9px] font-bold flex items-center gap-0.5 shadow-2xs transition-colors"
                      title="Reset to default voice (${escapeHtml(globalSpeakerVoice)})"
                      onclick="window.dubDubStore.clearSegmentVoiceOverride(${safeId})">
                      <span class="material-symbols-outlined text-xs">restart_alt</span>
                      <span class="hidden sm:inline">Reset</span>
                    </button>
                  ` : ''}

                  <button 
                    type="button"
                    data-action="seek-segment"
                    data-segment-id="${escapeHtml(seg.id)}"
                    class="h-7 px-2 rounded-md bg-amber-100 hover:bg-amber-200 text-[#8D4B00] text-xs font-bold flex items-center gap-1 transition-colors shadow-2xs" 
                    title="Audition Dubbed Audio"
                    onclick="window.dubDubStore.seekAndPlay(${seg.startSec || 0}, ${safeId})">
                    <span class="material-symbols-outlined text-sm">volume_up</span>
                    <span class="hidden sm:inline text-[10px]">Play</span>
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
