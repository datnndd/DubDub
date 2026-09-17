/**
 * Reusable VideoPlayer Component
 * Displays the video canvas, HUD telemetry, OCR overlays, and subtitle cards.
 */

export function renderVideoPlayer(state, options = {}) {
  const {
    title = "Synchronized Video Player",
    showOcrBox = false,
    showLipMeshBadge = false,
    showAudioSwitcher = false,
    showInpaintOverlay = false,
    aspectFitControls = false,
    subtitleVariant = "dual" // 'sample', 'dual', 'capcut'
  } = options;

  const currentSegment = state.segments.find(s => s.id === 2) || state.segments[0];
  const audioChan = state.playback.audioChannel;
  const renderedVideo = state.backend.outputs.find(output => /\.(mp4|mkv|webm)$/i.test(output.name));
  const previewUrl = renderedVideo?.url || state.project.previewUrl;

  return `
    <div class="h-full w-full bg-white rounded-xl border border-[#E7E4DC] shadow-xs flex flex-col min-h-0 overflow-hidden">
      <!-- Player Header Strip -->
      <div class="h-7.5 px-3 border-b border-[#E7E4DC] flex items-center justify-between bg-[#FAF9F6] flex-shrink-0">
        <div class="flex items-center gap-2">
          <span class="material-symbols-outlined text-[#8D4B00] text-sm">smart_display</span>
          <span class="text-xs font-bold text-stone-900">${title}</span>
          <span class="px-1.5 py-0.2 rounded text-[8px] font-mono font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
            ${state.project.resolution} • ${state.project.fps}
          </span>
        </div>

        <div class="flex items-center gap-2">
          ${showAudioSwitcher ? `
            <div class="flex items-center p-0.5 bg-stone-100 rounded-lg border border-stone-200 text-[10px]">
              <button 
                class="px-2 py-0.5 rounded transition-colors ${audioChan === 'orig' ? 'font-bold bg-white text-[#8D4B00] shadow-2xs border border-amber-200' : 'text-stone-500 hover:text-stone-800'}"
                onclick="window.dubDubStore.setAudioChannel('orig')">
                EN Orig
              </button>
              <button 
                class="px-2 py-0.5 rounded transition-colors ${audioChan === 'dub' ? 'font-bold bg-white text-[#8D4B00] shadow-2xs border border-amber-200' : 'text-stone-500 hover:text-stone-800'}"
                onclick="window.dubDubStore.setAudioChannel('dub')">
                ES Dub ★
              </button>
            </div>
          ` : ''}

          ${aspectFitControls ? `
            <div class="flex items-center gap-1 text-[10px]">
              <button class="px-1.5 py-0.5 rounded bg-stone-100 hover:bg-stone-200 text-stone-700 font-medium flex items-center gap-0.5 text-[9px]">
                <span class="material-symbols-outlined text-[10px]">aspect_ratio</span> 16:9
              </button>
              <button class="px-1.5 py-0.5 rounded bg-amber-50 text-[#8D4B00] border border-amber-300 font-bold text-[9px] flex items-center gap-0.5">
                <span class="material-symbols-outlined text-[10px]">fit_screen</span> Fit
              </button>
            </div>
          ` : ''}

          <span class="px-2 py-0.5 rounded bg-stone-100 text-stone-700 font-mono text-[10px] border border-stone-200 flex items-center gap-1">
            <span class="w-1.5 h-1.5 rounded-full bg-amber-500 warm-pulse"></span>
            <span>Cue #02</span>
          </span>
        </div>
      </div>

      <!-- Widescreen Visual Preview Container -->
      <div class="relative flex-1 min-h-0 bg-neutral-950 flex items-center justify-center overflow-hidden group">
        ${previewUrl ? `
          <video class="w-full h-full object-contain bg-black" src="${previewUrl}" controls></video>
        ` : `
          <img alt="Dubbing studio preview" class="w-full h-full object-cover opacity-90" src="assets/screen_2_broadcast_split.png" />
        `}
        <div class="absolute inset-0 bg-gradient-to-t from-black/85 via-transparent to-black/30 pointer-events-none"></div>

        <!-- Floating Badges Top -->
        <div class="absolute top-2 left-2.5 right-2.5 flex items-center justify-between pointer-events-none z-10">
          <div class="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-black/75 backdrop-blur-md text-amber-300 font-mono text-[10px] border border-amber-400/30">
            <span class="w-1.5 h-1.5 rounded-full bg-amber-400 warm-pulse"></span>
            <span>${state.playback.formattedTime} / ${state.project.duration}</span>
          </div>

          <div class="flex items-center gap-1.5">
            <span class="px-2 py-0.5 rounded-full bg-black/75 backdrop-blur-md text-white font-mono text-[10px] border border-white/15">
              ${state.speakers[0].name} (${state.speakers[0].role})
            </span>

            ${showLipMeshBadge ? `
              <span class="px-2 py-0.5 rounded-full bg-indigo-600/90 text-white font-bold text-[8px] uppercase tracking-wider backdrop-blur-md shadow-2xs flex items-center gap-1">
                <span class="material-symbols-outlined text-[10px]">face</span> AI Lip-Mesh Active
              </span>
            ` : `
              <span class="px-2 py-0.5 rounded-full bg-emerald-600/90 text-white font-bold text-[9px] uppercase tracking-wider shadow-2xs">
                Sync 99.8%
              </span>
            `}
          </div>
        </div>

        <!-- OCR Bounding Box Overlay (Stage 2) -->
        ${showOcrBox ? `
          <div class="absolute top-8 right-6 max-w-[320px] z-20 pointer-events-auto">
            <div class="relative p-2.5 rounded-lg bg-amber-950/85 backdrop-blur-md border-2 border-dashed border-amber-400 shadow-xl ring-2 ring-amber-500/30">
              <div class="absolute -top-2.5 left-2 px-1.5 py-0.2 bg-amber-500 text-stone-950 font-mono font-bold text-[9px] rounded uppercase tracking-wider flex items-center gap-1 shadow-xs">
                <span class="material-symbols-outlined text-[10px]">crop_free</span>
                <span>OCR BOX #01 • 99.4% Match</span>
              </div>
              <p class="text-amber-100 font-semibold text-xs leading-snug pt-1">
                “Translation must bridge cultural resonance, not merely literal syntax.”
              </p>
              <div class="flex items-center justify-between mt-1.5 pt-1 border-t border-amber-500/20 text-[9px] font-mono text-amber-300/80">
                <span>Detected on stage slide display</span>
                <span class="text-amber-200 underline cursor-pointer hover:text-white" onclick="alert('Pinned OCR Box #01 to Slide Inspector')">Pin to Inspector</span>
              </div>
            </div>
          </div>
        ` : ''}

        <!-- OCR Inpaint Overlay (Stage 4) -->
        ${showInpaintOverlay ? `
          <div class="absolute top-[14%] right-[6%] w-60 border-2 border-dashed border-amber-400 bg-amber-950/40 rounded-md p-1.5 backdrop-blur-[3px] shadow-xl z-20 transition-all">
            <div class="flex items-center justify-between -mt-3.5 -ml-1 mb-1">
              <span class="bg-[#8D4B00] text-amber-100 font-mono font-black text-[8px] px-1.5 py-0.5 rounded flex items-center gap-1 shadow-xs border border-amber-300/40">
                <span class="material-symbols-outlined text-[10px]">document_scanner</span> OCR VISUAL TARGET
              </span>
              <span class="bg-black/85 text-amber-300 text-[8px] font-mono px-1 rounded border border-amber-400/20">01:26.5</span>
            </div>
            <div class="bg-stone-950/90 rounded p-1.5 border border-amber-400/40 text-left space-y-1">
              <div class="text-[8px] text-stone-400 font-mono flex items-center justify-between">
                <span>Source Text:</span>
                <span class="text-stone-300 font-bold truncate max-w-[120px]">“GLOBAL INNOVATION SUMMIT”</span>
              </div>
              <div class="pt-1 border-t border-white/10">
                <div class="text-[9px] text-amber-300 font-bold leading-tight font-sans">
                  “CUMBRE GLOBAL DE INNOVACIÓN”
                </div>
                <div class="flex items-center justify-end gap-1 mt-1">
                  <button class="px-2 py-0.5 rounded bg-stone-800 hover:bg-stone-700 text-stone-200 font-semibold text-[8px] border border-stone-600 transition-colors">
                    Replace
                  </button>
                  <button class="px-2 py-0.5 rounded bg-[#8D4B00] hover:bg-amber-700 text-white font-bold text-[8px] uppercase tracking-wider flex items-center gap-0.5 shadow-xs transition-colors">
                    <span class="material-symbols-outlined text-[9px]">auto_fix_high</span> Inpaint
                  </button>
                </div>
              </div>
            </div>
          </div>
        ` : ''}

        <!-- Bottom Subtitle Bar Over Canvas -->
        <div class="absolute inset-x-3 bottom-2 z-20 flex justify-center text-center pointer-events-none">
          ${subtitleVariant === 'capcut' ? `
            <div class="max-w-xl bg-black/80 backdrop-blur-md px-4 py-1.5 rounded-xl border border-amber-400/40 shadow-2xl">
              <p class="text-amber-300 font-extrabold text-[13px] leading-snug tracking-tight drop-shadow-[0_2px_4px_rgba(0,0,0,0.9)]">
                “${currentSegment.targetText}”
              </p>
            </div>
          ` : subtitleVariant === 'dual' ? `
            <div class="w-full max-w-xl bg-black/85 backdrop-blur-md px-3.5 py-1.5 rounded-lg border border-amber-500/30 shadow-xl">
              <p class="text-white font-semibold text-xs leading-snug">
                “${currentSegment.targetText}”
              </p>
              <p class="text-amber-200/90 text-[10px] font-mono mt-0.5">
                EN: “${currentSegment.sourceText}”
              </p>
            </div>
          ` : `
            <div class="w-full max-w-lg bg-black/75 backdrop-blur-md px-3 py-1 rounded-lg border border-white/10">
              <p class="text-white text-xs font-medium truncate">
                Sample: “${currentSegment.sourceText}”
              </p>
            </div>
          `}
        </div>
      </div>
    </div>
  `;
}
