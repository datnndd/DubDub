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
  const selectedProvider = options.asrProviders.find(item => item.recognType === Number(backend.config.recognType))
    || options.asrProviders[0]
    || { id: '', label: 'Unavailable', models: [], requiresSettings: false, configured: false };
  const providerTags = options.asrProviders.map(provider =>
    `<option value="${provider.recognType}" ${provider.recognType === Number(backend.config.recognType) ? 'selected' : ''}>${escapeHtml(provider.label)}</option>`
  ).join('');
  const modelTags = selectedProvider.models.map(model =>
    `<option value="${escapeHtml(model)}" ${model === backend.config.modelName ? 'selected' : ''}>${escapeHtml(model)}</option>`
  ).join('');
  const speakerCountTags = ['No limit', '2 speakers', '3 speakers', '4 speakers', '5 speakers', '6 speakers', '7 speakers', '8 speakers', '9 speakers', '10 speakers'].map((label, value) =>
    `<option value="${value}" ${value === Number(state.engines.speakerCount) ? 'selected' : ''}>${label}</option>`
  ).join('');
  const settingsProvider = options.asrProviders.find(item => item.id === backend.asrSettingsProviderId);
  const selectedTranslation = options.translationProviders.find(item => item.translateType === Number(backend.config.translateType))
    || options.translationProviders[0]
    || { id: '', label: 'Unavailable', requiresSettings: false, configured: false };
  const translationTags = options.translationProviders.map(provider =>
    `<option value="${provider.translateType}" ${provider.translateType === Number(backend.config.translateType) ? 'selected' : ''}>${escapeHtml(provider.label)}</option>`
  ).join('');
  const translationModes = options.translationModes || [];
  const translationSettingsProvider = options.translationProviders.find(item => item.id === backend.translationSettingsProviderId);
  const timingModes = [
    { id: 'voice', title: 'Fit Dubbed Speech', detail: 'Speed up dubbed speech while preserving video timing' },
    { id: 'video', title: 'Fit Video to Speech', detail: 'Slow video when the translated speech runs longer' },
    { id: 'align', title: 'Align Subtitle & Audio', detail: 'Align timing without automatic speech or video speed changes' }
  ];

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

            <!-- Translation and timing mode -->
            <div>
              <label class="text-[9px] font-bold text-stone-400 uppercase tracking-wider block mb-1">Translation &amp; Timing Mode</label>
              <div class="space-y-1">
                ${timingModes.map(mode => `
                  <label class="p-1.5 rounded-lg border ${l.timingMode === mode.id ? 'border-[#8D4B00] bg-amber-50/60' : 'border-stone-200 bg-white hover:bg-stone-50'} flex items-start gap-2 cursor-pointer transition-all">
                    <input ${l.timingMode === mode.id ? 'checked' : ''} onchange="window.dubDubStore.updateTimingMode('${mode.id}')" class="mt-0.5 text-[#8D4B00] focus:ring-0 border-stone-300 w-3.5 h-3.5" name="timing_mode" value="${mode.id}" type="radio" />
                    <div>
                      <span class="text-[10px] font-bold text-stone-900 block leading-tight">${mode.title}</span>
                      <span class="text-[9px] text-stone-500 block leading-snug">${mode.detail}</span>
                    </div>
                  </label>
                `).join('')}
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
              <label class="text-[9px] font-bold text-stone-400 uppercase tracking-wider block mb-1">ASR Provider</label>
              <select class="w-full bg-white text-xs font-bold text-stone-800 py-1.5 px-2 rounded-lg border border-amber-300" onchange="window.dubDubStore.updateBackendConfig('recognType', Number(this.value))">
                ${providerTags}
              </select>
              <label class="text-[9px] font-bold text-stone-400 uppercase tracking-wider block mt-2 mb-1">Provider Model</label>
              <select class="w-full bg-white text-[10px] text-stone-700 py-1.5 px-2 rounded-lg border border-stone-200" onchange="window.dubDubStore.updateBackendConfig('modelName', this.value)">
                ${modelTags}
              </select>
              ${selectedProvider.requiresSettings || selectedProvider.testable ? `<div class="flex items-center gap-1.5 mt-2">
                ${selectedProvider.requiresSettings ? `
                  <button type="button" ${backend.asrTesting ? 'disabled' : ''} onclick="window.dubDubStore.openAsrSettings('${selectedProvider.id}')" title="Configure ${escapeHtml(selectedProvider.label)} API key" class="flex-1 h-7 px-2 rounded-lg border ${selectedProvider.configured ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-amber-300 bg-amber-50 text-[#8D4B00]'} text-[9px] font-bold flex items-center justify-center gap-1 disabled:opacity-50">
                    <span class="material-symbols-outlined text-xs">key</span>
                    API Settings
                  </button>
                ` : ''}
                ${selectedProvider.testable ? `
                  <button type="button" ${backend.asrTesting ? 'disabled' : ''} onclick="window.dubDubStore.testAsrConnection('${selectedProvider.id}')" class="${selectedProvider.requiresSettings ? 'flex-1' : 'w-full'} h-7 px-2 rounded-lg border border-stone-200 bg-stone-50 hover:bg-stone-100 disabled:opacity-50 text-stone-700 text-[9px] font-bold flex items-center justify-center gap-1">
                    <span class="material-symbols-outlined text-xs">${backend.asrTesting && backend.asrTestProviderId === selectedProvider.id ? 'progress_activity' : 'network_check'}</span>
                    ${backend.asrTesting && backend.asrTestProviderId === selectedProvider.id ? 'Testing…' : 'Test connection'}
                  </button>
                ` : ''}
              </div>` : ''}
              ${selectedProvider.requiresSettings ? `
                <p class="mt-1 text-[9px] ${selectedProvider.configured ? 'text-emerald-700' : 'text-amber-700'}">
                  ${selectedProvider.configured ? 'API credentials configured' : 'API credentials required before processing'}
                </p>
              ` : ''}
              ${backend.asrTestProviderId === selectedProvider.id && backend.asrTestMessage ? `
                <p class="mt-1 text-[9px] ${backend.asrTestOk === false ? 'text-red-700' : backend.asrTestOk ? 'text-emerald-700' : 'text-stone-500'} truncate" title="${escapeHtml(backend.asrTestMessage)}">${escapeHtml(backend.asrTestMessage)}</p>
              ` : ''}
            </div>

            <!-- Existing backend audio processing options -->
            <div>
              <label class="text-[9px] font-bold text-stone-400 uppercase tracking-wider block mb-1">Audio Processing</label>
              <div class="p-2 bg-stone-50 rounded-lg border border-stone-200/90 space-y-1.5">
                <label class="flex items-center justify-between cursor-pointer">
                  <div class="flex items-center gap-1.5 text-xs text-stone-800">
                    <input ${state.engines.speakerDiarization ? 'checked' : ''} onchange="window.dubDubStore.updateEngineConfig('speakerDiarization', this.checked)" class="rounded border-stone-300 text-[#8D4B00] focus:ring-0 w-3.5 h-3.5 bg-white" type="checkbox" />
                    <span class="font-medium text-[11px]">Speaker Classification</span>
                  </div>
                  <select aria-label="Number of speakers" ${state.engines.speakerDiarization ? '' : 'disabled'} onchange="window.dubDubStore.updateEngineConfig('speakerCount', Number(this.value))" class="max-w-24 rounded border border-stone-200 bg-white px-1 py-0.5 text-[9px] text-stone-600 disabled:bg-stone-100 disabled:text-stone-400">
                    ${speakerCountTags}
                  </select>
                </label>
                <div class="h-px bg-stone-200"></div>
                <label class="flex items-center justify-between cursor-pointer">
                  <div class="flex items-center gap-1.5 text-xs text-stone-800">
                    <input ${state.engines.removeNoise ? 'checked' : ''} onchange="window.dubDubStore.updateEngineConfig('removeNoise', this.checked)" class="rounded border-stone-300 text-[#8D4B00] focus:ring-0 w-3.5 h-3.5 bg-white" type="checkbox" />
                    <span class="font-medium text-[11px]">Noise Reduction</span>
                  </div>
                  <span class="text-[9px] font-mono text-stone-500">AI model · slower</span>
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
              <label class="text-[9px] font-bold text-stone-400 uppercase tracking-wider block mb-1">Translation Provider</label>
              <select class="w-full bg-white text-xs font-bold text-stone-800 py-1.5 px-2 rounded-lg border border-amber-300" onchange="window.dubDubStore.updateBackendConfig('translateType', Number(this.value))">
                ${translationTags}
              </select>
              <div class="flex items-center gap-1.5 mt-2">
                ${selectedTranslation.requiresSettings ? `
                  <button type="button" onclick="window.dubDubStore.openTranslationSettings('${selectedTranslation.id}')" class="flex-1 h-7 px-2 rounded-lg border ${selectedTranslation.configured ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-amber-300 bg-amber-50 text-[#8D4B00]'} text-[9px] font-bold flex items-center justify-center gap-1">
                    <span class="material-symbols-outlined text-xs">tune</span>
                    API Settings
                  </button>
                ` : ''}
                <button type="button" ${backend.translationTesting ? 'disabled' : ''} onclick="window.dubDubStore.testTranslationConnection('${selectedTranslation.id}')" class="${selectedTranslation.requiresSettings ? 'flex-1' : 'w-full'} h-7 px-2 rounded-lg border border-stone-200 bg-stone-50 hover:bg-stone-100 disabled:opacity-50 text-stone-700 text-[9px] font-bold flex items-center justify-center gap-1">
                  <span class="material-symbols-outlined text-xs">${backend.translationTesting && backend.translationTestProviderId === selectedTranslation.id ? 'progress_activity' : 'network_check'}</span>
                  ${backend.translationTesting && backend.translationTestProviderId === selectedTranslation.id ? 'Testing…' : 'Test connection'}
                </button>
              </div>
              ${selectedTranslation.requiresSettings ? `
                <p class="mt-1 text-[9px] ${selectedTranslation.configured ? 'text-emerald-700' : 'text-amber-700'}">
                  ${selectedTranslation.configured ? `${escapeHtml(selectedTranslation.model)} configured` : 'API settings required before processing'}
                </p>
              ` : ''}
              ${backend.translationTestProviderId === selectedTranslation.id && backend.translationTestMessage ? `
                <p class="mt-1 text-[9px] ${backend.translationTestOk === false ? 'text-red-700' : backend.translationTestOk ? 'text-emerald-700' : 'text-stone-500'} truncate" title="${escapeHtml(backend.translationTestMessage)}">${escapeHtml(backend.translationTestMessage)}</p>
              ` : ''}
            </div>

            <!-- Existing BaseTrans prompt modes -->
            <div>
              <label class="text-[9px] font-bold text-stone-400 uppercase tracking-wider block mb-1">Translation Mode</label>
              ${selectedTranslation.id === 'google' ? `
                <div class="p-2 rounded-lg bg-stone-50 border border-stone-200 text-[9px] text-stone-500">
                  Google Translate uses the existing line-by-line provider flow.
                </div>
              ` : `
                <div class="grid grid-cols-2 gap-1.5">
                  ${translationModes.map(mode => `
                    <label title="${escapeHtml(mode.description)}" class="p-1.5 rounded-lg border cursor-pointer ${backend.config.translationMode === mode.id ? 'border-[#8D4B00] bg-amber-50 text-[#8D4B00]' : 'border-stone-200 bg-stone-50 text-stone-600'}">
                      <input class="sr-only" type="radio" name="translation_mode" value="${mode.id}" ${backend.config.translationMode === mode.id ? 'checked' : ''} onchange="window.dubDubStore.updateBackendConfig('translationMode', this.value)" />
                      <span class="block text-[10px] font-bold">${escapeHtml(mode.label)}</span>
                      <span class="block mt-0.5 text-[8px] leading-tight text-stone-500">${escapeHtml(mode.description)}</span>
                    </label>
                  `).join('')}
                </div>
              `}
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
      ${settingsProvider ? `
        <div class="fixed inset-0 z-50 bg-stone-950/45 backdrop-blur-[1px] flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="asr-settings-title">
          <div class="w-full max-w-md rounded-xl border border-[#E7E4DC] bg-white shadow-2xl overflow-hidden">
            <div class="h-10 px-4 bg-[#FAF9F6] border-b border-[#E7E4DC] flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="material-symbols-outlined text-[#8D4B00] text-base">key</span>
                <h3 id="asr-settings-title" class="text-xs font-bold text-stone-900">${escapeHtml(settingsProvider.label)} API Settings</h3>
              </div>
              <button type="button" ${backend.asrSettingsSaving || backend.asrTesting ? 'disabled' : ''} onclick="window.dubDubStore.closeAsrSettings()" class="text-stone-400 hover:text-stone-700 disabled:opacity-40">
                <span class="material-symbols-outlined text-lg">close</span>
              </button>
            </div>
            <div class="p-4 space-y-3">
              <p class="text-[11px] text-stone-600">Enter the API key used by the local pyVideoTrans backend. Existing secrets are never sent to this screen.</p>
              <div>
                <label for="asr-api-key" class="text-[9px] font-bold text-stone-500 uppercase tracking-wider block mb-1">API Key</label>
                <input id="asr-api-key" type="password" autocomplete="new-password" ${backend.asrSettingsSaving || backend.asrTesting ? 'disabled' : ''} placeholder="${settingsProvider.configured ? 'Leave blank to keep the stored key' : 'Paste a new API key'}" class="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-xs text-stone-800 focus:outline-none focus:ring-1 focus:ring-[#8D4B00]" />
              </div>
              ${backend.asrSettingsError ? `<p class="rounded-lg border border-red-200 bg-red-50 px-2 py-1.5 text-[10px] text-red-700">${escapeHtml(backend.asrSettingsError)}</p>` : ''}
              ${backend.asrTestProviderId === settingsProvider.id && backend.asrTestMessage && backend.asrTestOk ? `<p class="rounded-lg border border-emerald-200 bg-emerald-50 px-2 py-1.5 text-[10px] text-emerald-700">${escapeHtml(backend.asrTestMessage)}</p>` : ''}
              <div class="flex items-center justify-end gap-2 pt-1">
                <button type="button" ${backend.asrSettingsSaving || backend.asrTesting ? 'disabled' : ''} onclick="window.dubDubStore.closeAsrSettings()" class="px-3 py-1.5 rounded-lg border border-stone-200 bg-white text-[10px] font-bold text-stone-600 disabled:opacity-40">Cancel</button>
                <button type="button" ${backend.asrSettingsSaving || backend.asrTesting ? 'disabled' : ''} onclick="window.dubDubStore.testAsrConnection('${settingsProvider.id}', true)" class="px-3 py-1.5 rounded-lg border border-[#8D4B00] bg-amber-50 text-[#8D4B00] text-[10px] font-bold disabled:opacity-50 flex items-center gap-1">
                  <span class="material-symbols-outlined text-xs">${backend.asrTesting ? 'progress_activity' : 'network_check'}</span>
                  ${backend.asrTesting ? 'Testing…' : 'Save & Test'}
                </button>
                <button type="button" ${backend.asrSettingsSaving || backend.asrTesting ? 'disabled' : ''} onclick="window.dubDubStore.saveAsrSettings()" class="px-3 py-1.5 rounded-lg bg-[#8D4B00] text-white text-[10px] font-bold disabled:opacity-50 flex items-center gap-1">
                  <span class="material-symbols-outlined text-xs">${backend.asrSettingsSaving ? 'progress_activity' : 'save'}</span>
                  ${backend.asrSettingsSaving ? 'Saving…' : 'Save API Key'}
                </button>
              </div>
            </div>
          </div>
        </div>
      ` : ''}
      ${translationSettingsProvider ? `
        <div class="fixed inset-0 z-50 bg-stone-950/45 backdrop-blur-[1px] flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="translation-settings-title">
          <div class="w-full max-w-lg rounded-xl border border-[#E7E4DC] bg-white shadow-2xl overflow-hidden">
            <div class="h-10 px-4 bg-[#FAF9F6] border-b border-[#E7E4DC] flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="material-symbols-outlined text-[#8D4B00] text-base">translate</span>
                <h3 id="translation-settings-title" class="text-xs font-bold text-stone-900">${escapeHtml(translationSettingsProvider.label)} Settings</h3>
              </div>
              <button type="button" ${backend.translationSettingsSaving || backend.translationTesting ? 'disabled' : ''} onclick="window.dubDubStore.closeTranslationSettings()" class="text-stone-400 hover:text-stone-700 disabled:opacity-40">
                <span class="material-symbols-outlined text-lg">close</span>
              </button>
            </div>
            <div class="p-4 space-y-3">
              <p class="text-[11px] text-stone-600">Configure the endpoint and model used by the local translation backend. Stored API keys are never returned to this screen.</p>
              <div>
                <label for="translation-base-url" class="text-[9px] font-bold text-stone-500 uppercase tracking-wider block mb-1">Base URL</label>
                <input id="translation-base-url" type="url" value="${escapeHtml(translationSettingsProvider.baseUrl)}" ${backend.translationSettingsSaving || backend.translationTesting ? 'disabled' : ''} placeholder="Use the provider default endpoint" class="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-xs text-stone-800 focus:outline-none focus:ring-1 focus:ring-[#8D4B00]" />
              </div>
              <div>
                <label for="translation-api-key" class="text-[9px] font-bold text-stone-500 uppercase tracking-wider block mb-1">API Key</label>
                <input id="translation-api-key" type="password" autocomplete="new-password" ${backend.translationSettingsSaving || backend.translationTesting ? 'disabled' : ''} placeholder="${translationSettingsProvider.configured ? 'Leave blank to keep the stored key' : 'Paste an API key'}" class="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-xs text-stone-800 focus:outline-none focus:ring-1 focus:ring-[#8D4B00]" />
              </div>
              <div>
                <label for="translation-model" class="text-[9px] font-bold text-stone-500 uppercase tracking-wider block mb-1">Model</label>
                <input id="translation-model" list="translation-model-options" value="${escapeHtml(translationSettingsProvider.model)}" ${backend.translationSettingsSaving || backend.translationTesting ? 'disabled' : ''} placeholder="Enter a model name" class="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-xs text-stone-800 focus:outline-none focus:ring-1 focus:ring-[#8D4B00]" />
                <datalist id="translation-model-options">
                  ${translationSettingsProvider.models.map(model => `<option value="${escapeHtml(model)}"></option>`).join('')}
                </datalist>
              </div>
              ${backend.translationSettingsError ? `<p class="rounded-lg border border-red-200 bg-red-50 px-2 py-1.5 text-[10px] text-red-700">${escapeHtml(backend.translationSettingsError)}</p>` : ''}
              ${backend.translationTestProviderId === translationSettingsProvider.id && backend.translationTestMessage && backend.translationTestOk ? `<p class="rounded-lg border border-emerald-200 bg-emerald-50 px-2 py-1.5 text-[10px] text-emerald-700">${escapeHtml(backend.translationTestMessage)}</p>` : ''}
              <div class="flex items-center justify-end gap-2 pt-1">
                <button type="button" ${backend.translationSettingsSaving || backend.translationTesting ? 'disabled' : ''} onclick="window.dubDubStore.closeTranslationSettings()" class="px-3 py-1.5 rounded-lg border border-stone-200 bg-white text-[10px] font-bold text-stone-600 disabled:opacity-40">Cancel</button>
                <button type="button" ${backend.translationSettingsSaving || backend.translationTesting ? 'disabled' : ''} onclick="window.dubDubStore.testTranslationConnection('${translationSettingsProvider.id}', true)" class="px-3 py-1.5 rounded-lg border border-[#8D4B00] bg-amber-50 text-[#8D4B00] text-[10px] font-bold disabled:opacity-50 flex items-center gap-1">
                  <span class="material-symbols-outlined text-xs">${backend.translationTesting ? 'progress_activity' : 'network_check'}</span>
                  ${backend.translationTesting ? 'Testing…' : 'Save & Test'}
                </button>
                <button type="button" ${backend.translationSettingsSaving || backend.translationTesting ? 'disabled' : ''} onclick="window.dubDubStore.saveTranslationSettings()" class="px-3 py-1.5 rounded-lg bg-[#8D4B00] text-white text-[10px] font-bold disabled:opacity-50 flex items-center gap-1">
                  <span class="material-symbols-outlined text-xs">${backend.translationSettingsSaving ? 'progress_activity' : 'save'}</span>
                  ${backend.translationSettingsSaving ? 'Saving…' : 'Save settings'}
                </button>
              </div>
            </div>
          </div>
        </div>
      ` : ''}
    </div>
  `;
}
