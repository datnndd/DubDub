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

  const currentSegment = state.segments.find(s => String(s.id) === String(state.activeSegmentId)) || state.segments[0] || {};
  const audioChan = state.playback.audioChannel;
  const renderedVideo = state.backend.outputs.find(output => /\.(mp4|mkv|webm)$/i.test(output.name));
  const previewUrl = renderedVideo?.url || state.project.previewUrl;

  const escapeHtml = value => String(value || '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);

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
            <span><span data-playhead-timecode>${state.playback.formattedTime}</span> / ${state.project.duration}</span>
          </span>
        </div>
      </div>

      <!-- Widescreen Visual Preview Container -->
      <div class="relative flex-1 min-h-0 bg-neutral-950 flex items-center justify-center overflow-hidden group">
        ${previewUrl ? `
          <video data-source-preview class="w-full h-full object-contain bg-black" src="${previewUrl}" controls preload="metadata"
            onloadedmetadata="window.dubDubStore.syncPreviewPlayback(this)"
            ontimeupdate="window.dubDubStore.syncPreviewPlayback(this)"
            onplay="window.dubDubStore.syncPreviewPlayback(this)"
            onpause="window.dubDubStore.syncPreviewPlayback(this)"></video>
        ` : `
          <img alt="Dubbing studio preview" class="w-full h-full object-cover opacity-90" src="assets/screen_2_broadcast_split.png" />
        `}


        <!-- Interactive PaddleOCR ROI Crop Box Overlay (Stage 2) -->
        ${state.ocrCrop && state.ocrCrop.active ? `
          <div data-crop-overlay class="absolute inset-0 z-30 pointer-events-auto flex flex-col justify-between p-2.5 bg-black/40 backdrop-blur-[2px]">
            <!-- Selection Box -->
            <div data-crop-box class="absolute border-2 border-dashed border-amber-400 bg-amber-950/40 rounded-lg shadow-2xl transition-all cursor-move select-none"
                 style="left: ${(state.ocrCrop.roi[0] * 100).toFixed(1)}%; top: ${(state.ocrCrop.roi[1] * 100).toFixed(1)}%; width: ${(state.ocrCrop.roi[2] * 100).toFixed(1)}%; height: ${(state.ocrCrop.roi[3] * 100).toFixed(1)}%;"
                 onpointerdown="window.dubDubStore.initRoiDrag(event, 'move')">
              <div class="absolute -top-6 left-0 px-2 py-0.5 bg-[#8D4B00] text-amber-100 rounded text-[9px] font-mono font-bold flex items-center gap-1 shadow-sm pointer-events-none">
                <span class="material-symbols-outlined text-[11px]">crop</span>
                <span>ROI CROP BOX • Segment #${state.ocrCrop.segmentId}</span>
              </div>
              <!-- 4 Interactive Corner Resize Handles -->
              <div class="absolute -top-1.5 -left-1.5 w-3.5 h-3.5 bg-amber-400 rounded-full cursor-nwse-resize hover:scale-125 transition-transform shadow-xs" onpointerdown="window.dubDubStore.initRoiDrag(event, 'nw')"></div>
              <div class="absolute -top-1.5 -right-1.5 w-3.5 h-3.5 bg-amber-400 rounded-full cursor-nesw-resize hover:scale-125 transition-transform shadow-xs" onpointerdown="window.dubDubStore.initRoiDrag(event, 'ne')"></div>
              <div class="absolute -bottom-1.5 -left-1.5 w-3.5 h-3.5 bg-amber-400 rounded-full cursor-nesw-resize hover:scale-125 transition-transform shadow-xs" onpointerdown="window.dubDubStore.initRoiDrag(event, 'sw')"></div>
              <div class="absolute -bottom-1.5 -right-1.5 w-3.5 h-3.5 bg-amber-400 rounded-full cursor-nwse-resize hover:scale-125 transition-transform shadow-xs" onpointerdown="window.dubDubStore.initRoiDrag(event, 'se')"></div>
            </div>

            <!-- Floating Control Bar -->
            <div class="mt-auto mx-auto bg-neutral-900/95 border border-amber-500/50 rounded-xl px-3 py-2 shadow-2xl flex flex-wrap items-center gap-2.5 backdrop-blur-md text-white text-xs z-40">
              <div class="flex items-center gap-1.5 text-amber-300 font-bold font-mono text-[11px]">
                <span class="material-symbols-outlined text-sm">document_scanner</span>
                <span>PaddleOCR ROI</span>
              </div>

              <!-- Region Presets -->
              <div class="flex items-center gap-1">
                <button class="px-2 py-0.5 rounded bg-stone-800 hover:bg-stone-700 text-stone-200 text-[10px] font-medium border border-stone-700"
                        onclick="window.dubDubStore.updateOcrRoi([0.05, 0.75, 0.90, 0.20])">
                  Bottom Subtitles
                </button>
                <button class="px-2 py-0.5 rounded bg-stone-800 hover:bg-stone-700 text-stone-200 text-[10px] font-medium border border-stone-700"
                        onclick="window.dubDubStore.updateOcrRoi([0.10, 0.60, 0.80, 0.25])">
                  Lower Third
                </button>
                <button class="px-2 py-0.5 rounded bg-stone-800 hover:bg-stone-700 text-stone-200 text-[10px] font-medium border border-stone-700"
                        onclick="window.dubDubStore.updateOcrRoi([0.05, 0.10, 0.90, 0.80])">
                  Full Frame
                </button>
              </div>

              <div class="h-4 w-px bg-stone-700"></div>

              <!-- Actions -->
              <div class="flex items-center gap-1.5">
                <button class="px-2.5 py-1 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-300 text-xs font-semibold"
                        onclick="window.dubDubStore.closeOcrCrop()">
                  Cancel
                </button>
                <button class="px-3 py-1 rounded-lg bg-[#8D4B00] hover:bg-[#743d00] text-white font-bold text-xs flex items-center gap-1 shadow-xs"
                        ${state.ocrCrop.loading ? 'disabled' : ''}
                        onclick="window.dubDubStore.confirmOcrCrop()">
                  ${state.ocrCrop.loading ? `
                    <span class="material-symbols-outlined text-xs animate-spin">progress_activity</span>
                    <span>Extracting Frames…</span>
                  ` : `
                    <span class="material-symbols-outlined text-xs">check</span>
                    <span>Confirm &amp; Replace</span>
                  `}
                </button>
              </div>

              ${state.ocrCrop.error ? `
                <span class="text-red-400 text-[10px] font-medium block w-full mt-1">${state.ocrCrop.error}</span>
              ` : ''}
            </div>
          </div>
        ` : ''}



        <!-- Bottom Subtitle Bar Over Canvas -->
        ${subtitleVariant === 'none' ? '' : `
        <div class="absolute inset-x-3 bottom-4 z-20 flex justify-center text-center pointer-events-none">
          ${subtitleVariant === 'capcut' ? `
            <div class="w-full max-w-2xl px-4 py-1 flex flex-col items-center">
              <span data-canvas-speaker-badge style="display: none;"></span>
              <p data-canvas-subtitle class="font-semibold text-center leading-snug tracking-wide select-none">
                ${escapeHtml(currentSegment?.targetText || currentSegment?.sourceText || currentSegment?.text || '')}
              </p>
            </div>
          ` : `
            <div class="w-full max-w-xl bg-black/85 backdrop-blur-md px-3.5 py-1.5 rounded-lg border border-amber-500/30 shadow-xl flex flex-col items-center">
              <div class="flex items-center gap-1.5 mb-0.5">
                <span data-canvas-speaker-badge class="px-2 py-0.5 rounded-full bg-[#8D4B00] text-white text-[9px] font-bold uppercase tracking-wider" style="${(currentSegment && (currentSegment.speakerName || currentSegment.speakerId)) ? '' : 'display: none;'}">
                  ${escapeHtml(currentSegment?.speakerName || currentSegment?.speakerLabel || currentSegment?.speaker || 'Speaker 1')}
                </span>
              </div>
              <p data-canvas-subtitle class="text-white font-semibold text-xs leading-snug">
                ${escapeHtml(currentSegment?.targetText || currentSegment?.sourceText || currentSegment?.text || '')}
              </p>
              ${currentSegment?.sourceText && currentSegment?.targetText ? `
                <p class="text-amber-200/80 text-[10px] font-mono mt-0.5">
                  ${escapeHtml((state.languages?.source?.code || 'EN').toUpperCase())}: ${escapeHtml(currentSegment.sourceText)}
                </p>
              ` : ''}
            </div>
          `}
        </div>
        `}
      </div>
    </div>
  `;
}
