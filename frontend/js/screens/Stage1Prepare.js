/**
 * Stage 1: Prepare Media & AI Model Setup
 * Command Deck for media ingest, language pairs, ASR, LLM, and voice pre-flight.
 */

export function renderStage1Prepare(state) {
  const p = state.project;
  const l = state.languages;
  const backend = state.backend;
  const options = backend.options;
  const escapeHtml = value => String(value || '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
  const ingestFailed = !p.verified && backend.status === 'failed';
  const ingestStatus = backend.status === 'analyzing' ? 'Inspecting' : ingestFailed ? 'Inspection Failed' : p.verified ? 'Valid Ingest' : 'Not Verified';
  const optionTags = (items, selected) => items.map(([value, label]) =>
    `<option value="${value}" ${String(value) === String(selected) ? 'selected' : ''}>${label}</option>`
  ).join('');
  const languageTags = (selected) => options.languages.map(item =>
    `<option value="${item.code}" ${item.code === selected ? 'selected' : ''}>${item.name} — ${item.code}</option>`
  ).join('');

  return `
    <div class="flex-1 min-h-0 w-full p-3 flex flex-col gap-2.5 overflow-hidden">
      <!-- TOP HERO MEDIA STRIP: Video Player Card & Rich Metadata Card (38% Height) -->
      <section class="h-[50%] min-h-0 flex-shrink-0 w-full grid grid-cols-12 gap-2.5">
        <!-- LEFT: 16:9 Video Snapshot & Live Waveform Preview (7 cols) -->
        <div class="col-span-12 md:col-span-7 h-full bg-white rounded-xl border border-[#E7E4DC] shadow-xs flex flex-col min-h-0 overflow-hidden">
          <!-- Card Header -->
          <div class="h-7 px-3 border-b border-[#E7E4DC] flex items-center justify-between bg-[#FAF9F6] flex-shrink-0">
            <div class="flex items-center gap-2">
              <span class="material-symbols-outlined text-[#8D4B00] text-sm">movie_filter</span>
              <span class="text-xs font-bold text-stone-900">Source Video &amp; Sound Canvas</span>
              <span class="px-1.5 py-0.2 rounded text-[9px] font-bold bg-amber-100 text-[#8D4B00] uppercase tracking-wide">${p.verified ? 'Media Verified' : 'Awaiting Media'}</span>
            </div>
            <div class="flex items-center gap-2 font-mono text-[10px] text-stone-500">
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
              <span>${p.hasAudio ? `Audio: ${p.audioCodec}` : 'Audio stream not verified'}</span>
            </div>
          </div>

          <!-- Widescreen Visual Preview -->
          <div class="relative flex-1 min-h-0 bg-neutral-950 flex items-center justify-center overflow-hidden group">
            ${p.previewUrl ? `
              <video data-source-preview class="w-full h-full object-contain bg-black" src="${p.previewUrl}" controls preload="metadata"
                onloadedmetadata="window.dubDubStore.syncPreviewPlayback(this)"
                ontimeupdate="window.dubDubStore.syncPreviewPlayback(this)"
                onplay="window.dubDubStore.syncPreviewPlayback(this)"
                onpause="window.dubDubStore.syncPreviewPlayback(this)"></video>
            ` : `
              <img 
                alt="Upload video placeholder" 
                class="w-full h-full object-contain p-8 opacity-80" 
                src="https://api.iconify.design/lucide:video-off.svg" 
              />
            `}
            <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/35 pointer-events-none"></div>

            <!-- Floating Badges Top -->
            <div class="absolute top-2 left-2.5 right-2.5 flex items-center justify-between pointer-events-none z-10">
              <div class="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-black/70 backdrop-blur-md text-amber-300 font-mono text-[10px] border border-amber-400/20">
                <span class="w-1.5 h-1.5 rounded-full bg-amber-400 warm-pulse"></span>
                <span><span data-preview-current>${state.playback.formattedTime}</span> / ${p.duration}</span>
              </div>
              <div class="flex items-center gap-1.5">
                <span class="px-2 py-0.5 rounded-full bg-black/70 backdrop-blur-md text-white font-mono text-[10px] border border-white/10">
                  ${p.resolution} • ${p.fps}
                </span>
                <span class="px-2 py-0.5 rounded-full bg-emerald-600/90 text-white font-bold text-[9px] uppercase tracking-wider">
                  ${p.verified ? 'Ready' : 'Inspecting'}
                </span>
              </div>
            </div>

            <!-- Center Quick Play Overlay Button -->
            <button 
              class="absolute z-10 w-11 h-11 rounded-full bg-[#8D4B00]/90 hover:bg-[#8D4B00] text-white flex items-center justify-center shadow-lg transition-transform hover:scale-105 active:scale-95 border border-amber-300/30"
              ${p.previewUrl ? '' : 'disabled'} onclick="window.dubDubStore.togglePlay()">
              <span data-preview-action-icon class="material-symbols-outlined text-2xl ml-0.5">${state.playback.isPlaying ? 'pause' : 'play_arrow'}</span>
            </button>

            <!-- Bottom Preview Snippet -->
            <div class="absolute inset-x-2 bottom-10 z-10 flex justify-center text-center pointer-events-none">
              <div class="w-full max-w-lg bg-black/75 backdrop-blur-md px-3 py-1 rounded-lg border border-white/10">
                <p class="text-white text-xs font-medium truncate">
                  ${p.verified ? 'Source media is ready for transcription and translation.' : 'Choose a video to inspect its metadata.'}
                </p>
              </div>
            </div>
          </div>

          <!-- Compact Audio Waveform Bar -->
          <div class="h-8 px-3 bg-[#FAF9F6] border-t border-[#E7E4DC] flex items-center gap-2.5 flex-shrink-0">
            <div class="flex items-center gap-1 font-mono text-[10px] text-stone-600">
              <span class="material-symbols-outlined text-xs text-[#8D4B00]">equalizer</span>
              <span>Waveform</span>
            </div>
            <input data-preview-timeline aria-label="Video timeline" class="flex-1 cursor-pointer disabled:cursor-not-allowed" type="range"
              min="0" max="${p.durationSec || 0}" step="0.01" value="${state.playback.currentTime}"
              ${p.previewUrl ? '' : 'disabled'} oninput="window.dubDubStore.seekPreview(this.value)" />
            <span class="font-mono text-[10px] text-stone-500 font-semibold"><span data-preview-current>${state.playback.formattedTime}</span> / ${p.duration}</span>
          </div>
        </div>

        <!-- RIGHT: Rich File Metadata & Voice Diagnostics Card (5 cols) -->
        <div class="col-span-12 md:col-span-5 h-full bg-white rounded-xl border border-[#E7E4DC] shadow-xs flex flex-col min-h-0 overflow-hidden">
          <div class="h-7 px-3 border-b border-[#E7E4DC] flex items-center justify-between bg-[#FAF9F6] flex-shrink-0">
            <div class="flex items-center gap-2">
              <span class="material-symbols-outlined text-[#8D4B00] text-sm">description</span>
              <span class="text-xs font-bold text-stone-900">Media Ingest Diagnostics</span>
            </div>
            <span class="text-[10px] font-mono ${ingestFailed ? 'text-red-700 bg-red-50 border-red-200' : p.verified ? 'text-emerald-700 bg-emerald-50 border-emerald-200' : 'text-stone-500 bg-stone-50 border-stone-200'} px-2 py-0.5 rounded border font-medium">${ingestStatus}</span>
          </div>

          <div class="flex-1 min-h-0 p-3 flex flex-col justify-between">
            <!-- File identity -->
            <div class="flex items-start justify-between">
              <div>
                <h4 class="text-xs font-bold text-stone-900 truncate max-w-[280px]">${p.filename}</h4>
                <p class="text-[10px] text-stone-500 font-mono mt-0.5">${p.fileSize} • Container: ${p.format}</p>
              </div>
              <span class="px-2 py-0.5 rounded-full bg-amber-50 border border-amber-200 text-[#8D4B00] font-mono text-[10px] font-bold">
                ${p.resolution} @ ${p.fps}
              </span>
            </div>

            ${ingestFailed ? `
              <div class="px-2 py-1.5 rounded-lg bg-red-50 border border-red-200 text-[10px] text-red-700">
                ${escapeHtml(backend.error)}
              </div>
            ` : ''}

            <!-- 4 Grid Technical Specs -->
            <div class="grid grid-cols-4 gap-1.5 py-1">
              <div class="p-1.5 rounded-lg bg-stone-50 border border-stone-200/80">
                <span class="text-[9px] text-stone-400 block font-medium">Duration</span>
                <span class="text-[11px] font-mono font-bold text-stone-800">${p.duration}</span>
              </div>
              <div class="p-1.5 rounded-lg bg-stone-50 border border-stone-200/80">
                <span class="text-[9px] text-stone-400 block font-medium">Video Codec</span>
                <span class="text-[11px] font-mono font-bold text-stone-800">${p.videoCodec}</span>
              </div>
              <div class="p-1.5 rounded-lg bg-stone-50 border border-stone-200/80">
                <span class="text-[9px] text-stone-400 block font-medium">Audio Codec</span>
                <span class="text-[11px] font-mono font-bold text-stone-800">${p.audioCodec}</span>
              </div>
              <div class="p-1.5 rounded-lg bg-stone-50 border border-stone-200/80">
                <span class="text-[9px] text-stone-400 block font-medium">Bitrate</span>
                <span class="text-[11px] font-mono font-bold text-stone-800">${p.bitrate}</span>
              </div>
            </div>

            <!-- Speaker Diarization Preview Chip -->
            <div class="p-2 rounded-lg bg-amber-50/60 border border-amber-200/90 flex items-center gap-2">
              <div class="w-6 h-6 rounded-full bg-amber-500/20 text-[#8D4B00] flex items-center justify-center flex-shrink-0">
                <span class="material-symbols-outlined text-sm">record_voice_over</span>
              </div>
              <div class="min-w-0">
                <div class="text-[11px] font-bold text-stone-900 leading-none">${p.hasAudio ? 'Audio stream detected' : 'No audio stream detected'}</div>
                <div class="text-[10px] text-stone-600 truncate mt-0.5">Speaker analysis runs during the processing workflow.</div>
              </div>
            </div>

            <!-- Action Buttons -->
            <div class="flex items-center gap-2 pt-1 border-t border-stone-200">
              <button ${['analyzing', 'submitting', 'queued', 'running'].includes(backend.status) ? 'disabled' : ''} onclick="window.dubDubStore.chooseMedia()" class="flex-1 py-1.5 px-2 rounded-lg bg-stone-100 hover:bg-stone-200 disabled:text-stone-400 disabled:cursor-not-allowed text-stone-700 text-xs font-semibold border border-stone-200 transition-colors flex items-center justify-center gap-1">
                <span class="material-symbols-outlined text-sm text-stone-500">upload_file</span>
                <span>Replace Video</span>
              </button>
              <button disabled title="Audio stem preview is not connected yet" class="flex-1 py-1.5 px-2 rounded-lg bg-stone-50 text-stone-400 text-xs font-bold border border-stone-200 flex items-center justify-center gap-1 cursor-not-allowed">
                <span class="material-symbols-outlined text-sm">headphones</span>
                <span>Preview Audio Stems</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- BOTTOM CONFIGURATION GRID: fills the remaining height -->
      <section class="flex-1 min-h-0 w-full grid grid-cols-12 gap-2.5">
        <!-- QUADRANT 1: Source & Target Languages (3 cols) -->
        <div class="col-span-12 md:col-span-6 lg:col-span-3 h-full bg-white rounded-xl border border-[#E7E4DC] shadow-xs flex flex-col min-h-0 overflow-hidden">
          <div class="h-7 px-3 border-b border-[#E7E4DC] bg-[#FAF9F6] flex items-center justify-between flex-shrink-0">
            <div class="flex items-center gap-1.5">
              <span class="material-symbols-outlined text-[#8D4B00] text-sm">translate</span>
              <h3 class="text-xs font-bold text-stone-900">1. Languages &amp; Mode</h3>
            </div>
            <span class="px-1.5 py-0.2 bg-stone-100 text-stone-600 rounded text-[9px] font-mono font-bold">Step 1A</span>
          </div>
          <div class="flex-1 min-h-0 p-3 flex flex-col justify-between overflow-y-auto space-y-2">
            <!-- Source Lang -->
            <div>
              <label class="text-[9px] font-bold text-stone-400 uppercase tracking-wider block mb-1">Source Audio Language</label>
              <select class="w-full bg-white text-xs font-bold text-stone-800 py-1.5 px-2.5 rounded-lg border border-stone-200" onchange="window.dubDubStore.updateSourceLanguage(this.value, this.options[this.selectedIndex].text)">
                ${languageTags(l.source.code)}
              </select>
            </div>

            <!-- Target Lang with Switcher -->
            <div>
              <div class="flex items-center justify-between mb-1">
                <label class="text-[9px] font-bold text-stone-400 uppercase tracking-wider">Target Dubbing Language</label>
                <span class="material-symbols-outlined text-xs text-stone-400 hover:text-stone-700 cursor-pointer" title="Swap languages">swap_vert</span>
              </div>
              <select 
                class="w-full bg-white text-xs font-bold text-stone-800 py-1.5 pl-2.5 pr-7 rounded-lg border border-amber-300 focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer shadow-2xs"
                onchange="window.dubDubStore.updateTargetLanguage(this.value, this.options[this.selectedIndex].text)">
                ${languageTags(l.target.code)}
              </select>
            </div>

            <!-- Translation Mode Toggle -->
            <div>
              <label class="text-[9px] font-bold text-stone-400 uppercase tracking-wider block mb-1">Translation &amp; Timing Mode</label>
              <div class="space-y-1.5">
                <label class="p-2 rounded-lg border-2 border-[#8D4B00] bg-amber-50/50 flex items-start gap-2 cursor-pointer transition-all">
                  <input disabled checked class="mt-0.5 text-[#8D4B00] focus:ring-0 border-stone-300 w-3.5 h-3.5" name="translation_mode" type="radio" />
                  <div>
                    <span class="text-[11px] font-bold text-stone-900 block leading-tight">Idiomatic Dubbing</span>
                    <span class="text-[10px] text-stone-600 block leading-snug">Adapts length for natural lip synchronization</span>
                  </div>
                </label>
                <label class="p-2 rounded-lg border border-stone-200 bg-white hover:bg-stone-50 flex items-start gap-2 cursor-pointer transition-all">
                  <input disabled class="mt-0.5 text-[#8D4B00] focus:ring-0 border-stone-300 w-3.5 h-3.5" name="translation_mode" type="radio" />
                  <div>
                    <span class="text-[11px] font-bold text-stone-800 block leading-tight">Direct Subtitle Mode</span>
                    <span class="text-[10px] text-stone-500 block leading-snug">Literal fidelity, best for academic accuracy</span>
                  </div>
                </label>
              </div>
            </div>
          </div>
        </div>

        <!-- QUADRANT 2: Speech Recognition / ASR Engine (3 cols) -->
        <div class="col-span-12 md:col-span-6 lg:col-span-3 h-full bg-white rounded-xl border border-[#E7E4DC] shadow-xs flex flex-col min-h-0 overflow-hidden">
          <div class="h-7 px-3 border-b border-[#E7E4DC] bg-[#FAF9F6] flex items-center justify-between flex-shrink-0">
            <div class="flex items-center gap-1.5">
              <span class="material-symbols-outlined text-[#8D4B00] text-sm">hearing</span>
              <h3 class="text-xs font-bold text-stone-900">2. Speech Recognition (ASR)</h3>
            </div>
            <span class="px-1.5 py-0.2 bg-stone-100 text-stone-600 rounded text-[9px] font-mono font-bold">Transcribe</span>
          </div>
          <div class="flex-1 min-h-0 p-3 flex flex-col justify-between overflow-y-auto space-y-2">
            <div>
              <label class="text-[9px] font-bold text-stone-400 uppercase tracking-wider block mb-1">Select ASR Foundation Model</label>
              <select class="w-full bg-white text-xs font-bold text-stone-800 py-1.5 px-2 rounded-lg border border-amber-300" onchange="window.dubDubStore.updateBackendConfig('recognType', Number(this.value))">
                ${optionTags(options.recognizers, backend.config.recognType)}
              </select>
              <select class="w-full mt-2 bg-white text-[10px] text-stone-700 py-1.5 px-2 rounded-lg border border-stone-200" onchange="window.dubDubStore.updateBackendConfig('modelName', this.value)">
                ${options.models.map(model => `<option ${model === backend.config.modelName ? 'selected' : ''}>${model}</option>`).join('')}
              </select>
            </div>

            <!-- Audio Enhancements Checkboxes -->
            <div>
              <label class="text-[9px] font-bold text-stone-400 uppercase tracking-wider block mb-1">Pre-processing Filters</label>
              <div class="p-2 bg-stone-50 rounded-lg border border-stone-200/90 space-y-1.5">
                <label class="flex items-center justify-between cursor-pointer">
                  <div class="flex items-center gap-1.5 text-xs text-stone-800">
                    <input ${state.engines.speakerDiarization ? 'checked' : ''} onchange="window.dubDubStore.state.engines.speakerDiarization=this.checked" class="rounded border-stone-300 text-[#8D4B00] focus:ring-0 w-3.5 h-3.5 bg-white" type="checkbox" />
                    <span class="font-medium text-[11px]">Speaker Diarization</span>
                  </div>
                  <span class="text-[9px] font-mono text-stone-500">Auto-isolate</span>
                </label>
                <div class="h-px bg-stone-200"></div>
                <label class="flex items-center justify-between cursor-pointer">
                  <div class="flex items-center gap-1.5 text-xs text-stone-800">
                    <input ${state.engines.removeBackgroundNoise ? 'checked' : ''} onchange="window.dubDubStore.state.engines.removeBackgroundNoise=this.checked" class="rounded border-stone-300 text-[#8D4B00] focus:ring-0 w-3.5 h-3.5 bg-white" type="checkbox" />
                    <span class="font-medium text-[11px]">Remove Background Noise</span>
                  </div>
                  <span class="text-[9px] font-mono text-stone-500">-24 dB de-reverb</span>
                </label>
              </div>
            </div>
          </div>
        </div>

        <!-- QUADRANT 3: Translation LLM Engine (3 cols) -->
        <div class="col-span-12 md:col-span-6 lg:col-span-3 h-full bg-white rounded-xl border border-[#E7E4DC] shadow-xs flex flex-col min-h-0 overflow-hidden">
          <div class="h-7 px-3 border-b border-[#E7E4DC] bg-[#FAF9F6] flex items-center justify-between flex-shrink-0">
            <div class="flex items-center gap-1.5">
              <span class="material-symbols-outlined text-[#8D4B00] text-sm">psychology</span>
              <h3 class="text-xs font-bold text-stone-900">3. Translation LLM</h3>
            </div>
            <span class="px-1.5 py-0.2 bg-stone-100 text-stone-600 rounded text-[9px] font-mono font-bold">Reasoning</span>
          </div>
          <div class="flex-1 min-h-0 p-3 flex flex-col justify-between overflow-y-auto space-y-2">
            <div>
              <label class="text-[9px] font-bold text-stone-400 uppercase tracking-wider block mb-1">Target Engine Model</label>
              <select class="w-full bg-white text-xs font-bold text-stone-800 py-1.5 px-2 rounded-lg border border-amber-300" onchange="window.dubDubStore.updateBackendConfig('translateType', Number(this.value))">
                ${optionTags(options.translators, backend.config.translateType)}
              </select>
            </div>

            <!-- Tone Preset Pills -->
            <div>
              <label class="text-[9px] font-bold text-stone-400 uppercase tracking-wider block mb-1">Tone &amp; Register Preset</label>
              <div class="grid grid-cols-2 gap-1.5">
                <button disabled title="Tone presets are not connected yet" class="py-1 px-1.5 rounded-lg text-[10px] font-bold bg-stone-200 text-stone-500 text-center cursor-not-allowed">
                  Conversational ★
                </button>
                <button disabled class="py-1 px-1.5 rounded-lg text-[10px] font-medium bg-stone-50 text-stone-400 border border-stone-200 text-center cursor-not-allowed">
                  Formal Lecture
                </button>
                <button disabled class="py-1 px-1.5 rounded-lg text-[10px] font-medium bg-stone-50 text-stone-400 border border-stone-200 text-center cursor-not-allowed">
                  Colloquial Youth
                </button>
                <button disabled class="py-1 px-1.5 rounded-lg text-[10px] font-medium bg-stone-50 text-stone-400 border border-stone-200 text-center cursor-not-allowed">
                  Technical / Science
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- QUADRANT 4: Synthesis & Voice Clone Pre-flight (3 cols) -->
        <div class="col-span-12 md:col-span-6 lg:col-span-3 h-full bg-white rounded-xl border border-[#E7E4DC] shadow-xs flex flex-col min-h-0 overflow-hidden">
          <div class="h-7 px-3 border-b border-[#E7E4DC] bg-[#FAF9F6] flex items-center justify-between flex-shrink-0">
            <div class="flex items-center gap-1.5">
              <span class="material-symbols-outlined text-[#8D4B00] text-sm">settings_voice</span>
              <h3 class="text-xs font-bold text-stone-900">4. Voice Clone Pre-flight</h3>
            </div>
            <span class="px-1.5 py-0.2 bg-stone-100 text-stone-600 rounded text-[9px] font-mono font-bold">TTS Matrix</span>
          </div>
          <div class="flex-1 min-h-0 p-3 flex flex-col justify-between overflow-y-auto space-y-2">
            <div class="grid grid-cols-1 gap-1.5">
              <select class="w-full bg-white text-[10px] font-bold py-1.5 px-2 rounded-lg border border-amber-300" onchange="window.dubDubStore.updateBackendConfig('ttsType', Number(this.value))">
                ${optionTags(options.voices, backend.config.ttsType)}
              </select>
              <select class="w-full bg-white text-[10px] py-1.5 px-2 rounded-lg border border-stone-200" onchange="window.dubDubStore.updateBackendConfig('voiceRole', this.value)">
                ${(options.voiceRoles || ['No']).map(voice => `<option ${voice === backend.config.voiceRole ? 'selected' : ''}>${voice}</option>`).join('')}
              </select>
            </div>
            <div class="space-y-1.5">
              <label class="text-[9px] font-bold text-stone-400 uppercase tracking-wider block">Voice Mapping</label>
              <div class="p-3 rounded-lg bg-stone-50 border border-stone-200 flex items-start gap-2">
                <span class="material-symbols-outlined text-base text-stone-400">group</span>
                <div>
                  <div class="text-[11px] font-bold text-stone-700">Available after transcription</div>
                  <div class="text-[10px] text-stone-500 mt-0.5">Per-speaker voice assignment is not part of the Prepare stage yet.</div>
                </div>
              </div>
            </div>

            <!-- Pre-flight estimate telemetry box -->
            <div class="p-2 rounded-lg bg-stone-100/90 border border-stone-200/80">
              <div class="flex items-center gap-1 text-[10px] font-bold text-stone-700">
                <span class="material-symbols-outlined text-xs text-[#8D4B00]">speed</span>
                <span>Processing Estimate</span>
              </div>
              <p class="text-[10px] text-stone-600 font-mono mt-0.5">
                Estimate becomes available after a processing run starts.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  `;
}
