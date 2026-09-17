/**
 * Stage 4: Master Video & Timeline Editor
 * CapCut Desktop Pro Timeline Deck with multi-track NLE, dynamic subtitle styling, and OCR inpainting.
 */

export function renderStage4EditVideo(state) {
  const p = state.project;
  const sub = state.subtitleStyles;
  const curTime = state.playback.currentTime;
  const playheadPercent = Math.min(100, (curTime / state.project.durationSec) * 100);

  return `
    <div class="flex-1 min-h-0 w-full p-2 flex flex-col gap-2 overflow-hidden">
      <!-- TOP AI ENHANCERS STRIP -->
      <div class="h-8 flex-shrink-0 bg-white border border-[#E4DEC3] rounded-lg px-3 flex items-center justify-between shadow-2xs">
        <div class="flex items-center gap-1 bg-[#FAF8F5] p-0.5 rounded-lg border border-stone-200">
          <label class="flex items-center gap-1 px-2 py-0.5 rounded bg-white border border-amber-300 shadow-2xs text-[10px] font-bold text-[#8D4B00] cursor-pointer">
            <input 
              checked 
              class="w-2.5 h-2.5 rounded text-[#8D4B00] focus:ring-0" 
              type="checkbox"
              onchange="window.dubDubStore.updateSubtitleStyle('aiLipSync', this.checked)" 
            />
            <span>AI Lip-Sync</span>
          </label>
          <label class="flex items-center gap-1 px-2 py-0.5 rounded bg-white border border-stone-200 text-[10px] font-semibold text-stone-700 cursor-pointer">
            <input 
              checked 
              class="w-2.5 h-2.5 rounded text-[#8D4B00] focus:ring-0" 
              type="checkbox"
              onchange="window.dubDubStore.updateSubtitleStyle('deReverb', this.checked)"
            />
            <span>De-reverb</span>
          </label>
          <label class="flex items-center gap-1 px-2 py-0.5 rounded hover:bg-white text-[10px] font-medium text-stone-600 cursor-pointer">
            <input 
              class="w-2.5 h-2.5 rounded text-[#8D4B00] focus:ring-0" 
              type="checkbox"
              onchange="window.dubDubStore.updateSubtitleStyle('faceRetouch', this.checked)"
            />
            <span>Face Retouch</span>
          </label>
          <label class="flex items-center gap-1 px-2 py-0.5 rounded bg-white border border-stone-200 text-[10px] font-semibold text-stone-700 cursor-pointer">
            <input 
              checked 
              class="w-2.5 h-2.5 rounded text-[#8D4B00] focus:ring-0" 
              type="checkbox"
              onchange="window.dubDubStore.updateSubtitleStyle('superRes4K', this.checked)"
            />
            <span class="text-amber-900">4K Super-Res</span>
          </label>
        </div>

        <div class="flex items-center gap-2">
          <div class="flex items-center gap-1 text-[11px] text-emerald-700 font-semibold bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200">
            <span class="material-symbols-outlined text-xs">cloud_done</span>
            <span class="text-[10px]">CapCut Timeline Synced</span>
          </div>
        </div>
      </div>

      <!-- MIDDLE ROW: MONITOR (7 Cols) & DUAL-TABBED INSPECTOR (5 Cols) (50% Height) -->
      <div class="h-[48%] min-h-0 grid grid-cols-12 gap-2">
        <!-- MONITOR VIEWPORT (7 Cols) -->
        <section class="col-span-12 lg:col-span-7 h-full bg-white rounded-xl border border-[#E4DEC3] shadow-xs flex flex-col overflow-hidden min-h-0">
          <div class="h-7 px-3 border-b border-[#E4DEC3] bg-[#FAF8F5] flex items-center justify-between flex-shrink-0">
            <div class="flex items-center gap-2">
              <span class="material-symbols-outlined text-[#8D4B00] text-sm">smart_display</span>
              <span class="text-[11px] font-bold text-stone-900 tracking-tight">Program Out Monitor</span>
              <span class="px-1.5 py-0.1 rounded text-[8px] font-mono font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                4K 60FPS MASTER
              </span>
            </div>
            <div class="flex items-center gap-1.5 text-[10px]">
              <span class="text-stone-400 font-mono text-[9px]">Zoom: 100%</span>
              <button class="px-1.5 py-0.5 rounded bg-stone-100 hover:bg-stone-200 text-stone-700 font-medium flex items-center gap-0.5 text-[9px]">
                <span class="material-symbols-outlined text-[10px]">aspect_ratio</span> 16:9
              </button>
              <button class="px-1.5 py-0.5 rounded bg-amber-50 text-[#8D4B00] border border-amber-300 font-bold text-[9px] flex items-center gap-0.5">
                <span class="material-symbols-outlined text-[10px]">fit_screen</span> Fit
              </button>
            </div>
          </div>

          <!-- Video Canvas Container -->
          <div class="relative flex-1 min-h-0 bg-[#0B0E15] flex items-center justify-center overflow-hidden">
            <img 
              alt="Program Out Master Frame" 
              class="w-full h-full object-cover opacity-90" 
              src="assets/screen_2_broadcast_split.png" 
              onerror="this.src='https://lh3.googleusercontent.com/aida-public/AB6AXuAdw2oYibvlA_Z6ofNA2ic_IGcy9kFrw9CXigxphiomgTQrVilzO3B-RsHzuoK_uOBcMKomeOI3p0ZBGO9Ht95RZmprC7QLSxJ-dV0D-Wms50T6hieKj6GKnYUKlPFgnbNpHa3nkNCMZph4Ix6ryFk3npfM9bec-SuJubanr_mcfadH-lnT7PUTrBFeOBr4GO3m3u5ieaYBX3inE867dYZl1pGK6hBigQ6plLLpfi8FOoEhA-2Gf42NJw'"
            />

            <!-- Top Monitor HUD Telemetry -->
            <div class="absolute top-2 left-2.5 right-2.5 flex items-center justify-between pointer-events-none z-10">
              <div class="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-black/80 backdrop-blur-md text-amber-300 font-mono text-[10px] border border-amber-400/30">
                <span class="w-1.5 h-1.5 rounded-full bg-amber-400 warm-pulse"></span>
                <span>${state.playback.formattedTime} / ${p.duration}</span>
              </div>
              <div class="flex items-center gap-1.5">
                <span class="px-2 py-0.5 rounded-full bg-indigo-600/90 text-white font-bold text-[8px] uppercase tracking-wider backdrop-blur-md shadow-xs flex items-center gap-1">
                  <span class="material-symbols-outlined text-[10px]">face</span> AI Lip-Mesh Active
                </span>
                <span class="px-2 py-0.5 rounded-full bg-black/70 text-amber-200 font-mono text-[8px] border border-white/10 backdrop-blur-md">
                  Ducking: -14dB
                </span>
              </div>
            </div>

            <!-- OCR INPAINTING BOUNDING BOX OVERLAY -->
            <div class="absolute top-[14%] right-[7%] w-60 border-2 border-dashed border-amber-400 bg-amber-950/40 rounded-md p-1.5 backdrop-blur-[3px] shadow-xl z-20 transition-all">
              <div class="flex items-center justify-between -mt-3.5 -ml-1 mb-1">
                <span class="bg-[#8D4B00] text-amber-100 font-mono font-black text-[8px] px-1.5 py-0.5 rounded flex items-center gap-1 shadow-xs border border-amber-300/40">
                  <span class="material-symbols-outlined text-[10px]">document_scanner</span> OCR TARGET
                </span>
                <span class="bg-black/85 text-amber-300 text-[8px] font-mono px-1 rounded border border-amber-400/20">01:26.5</span>
              </div>
              <div class="bg-stone-950/90 rounded p-1.5 border border-amber-400/40 text-left space-y-1">
                <div class="text-[8px] text-stone-400 font-mono flex items-center justify-between">
                  <span>Source Sign:</span>
                  <span class="text-stone-300 font-bold truncate max-w-[120px]">“GLOBAL INNOVATION”</span>
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

            <!-- Dynamic Subtitle Overlay with Custom Styling -->
            <div class="absolute inset-x-4 bottom-3 z-20 flex justify-center text-center pointer-events-none">
              <div class="max-w-lg bg-black/80 backdrop-blur-md px-4 py-1.5 rounded-xl border border-amber-400/40 shadow-2xl">
                <p 
                  class="text-amber-300 font-extrabold text-[13px] leading-snug tracking-tight drop-shadow-[0_2px_4px_rgba(0,0,0,0.9)]"
                  style="font-family: '${sub.fontFamily}'; font-size: ${sub.fontSize * 0.55}px; color: ${sub.color};">
                  “${state.segments[0].targetText}”
                </p>
              </div>
            </div>
          </div>

          <!-- Mini-Transport Controls Bar -->
          <div class="h-7 px-3 bg-[#FAF8F5] border-t border-[#E4DEC3] flex items-center justify-between flex-shrink-0">
            <div class="flex items-center gap-1 text-stone-600">
              <button class="p-0.5 hover:bg-stone-200 rounded" onclick="window.dubDubStore.setPlaybackTime(Math.max(0, ${curTime} - 5))"><span class="material-symbols-outlined text-[13px]">replay_5</span></button>
              <button 
                class="w-5 h-5 rounded-full bg-[#8D4B00] text-white flex items-center justify-center shadow-xs hover:bg-[#743d00]"
                onclick="window.dubDubStore.togglePlay()">
                <span class="material-symbols-outlined text-[12px]">${state.playback.isPlaying ? 'pause' : 'play_arrow'}</span>
              </button>
              <button class="p-0.5 hover:bg-stone-200 rounded" onclick="window.dubDubStore.setPlaybackTime(Math.min(${p.durationSec}, ${curTime} + 5))"><span class="material-symbols-outlined text-[13px]">forward_5</span></button>
            </div>
            <button class="text-[9px] text-[#8D4B00] font-bold hover:underline flex items-center gap-1" onclick="alert('Visual OCR Scanner active across video keyframes')">
              <span class="material-symbols-outlined text-[11px]">center_focus_strong</span> Scan On-Screen Signs (Visual OCR)
            </button>
          </div>
        </section>

        <!-- DUAL TABBED INSPECTOR (5 Cols) -->
        <aside class="col-span-12 lg:col-span-5 h-full bg-white rounded-xl border border-[#E4DEC3] shadow-xs flex flex-col overflow-hidden min-h-0">
          <!-- Segmented Tab Header -->
          <div class="p-1 border-b border-[#E4DEC3] bg-[#FAF8F5] flex items-center justify-between flex-shrink-0">
            <div class="flex items-center gap-1 bg-stone-200/70 p-0.5 rounded-lg w-full max-w-[280px]">
              <button 
                class="flex-1 py-1 rounded-md text-[10px] font-bold ${sub.activeTab === 'text' ? 'bg-white text-[#8D4B00] shadow-xs border border-amber-300' : 'text-stone-600 hover:text-stone-900'} flex items-center justify-center gap-1"
                onclick="window.dubDubStore.updateSubtitleStyle('activeTab', 'text')">
                <span class="material-symbols-outlined text-xs">format_size</span> Text &amp; Fonts
              </button>
              <button 
                class="flex-1 py-1 rounded-md text-[10px] font-semibold ${sub.activeTab === 'bgm' ? 'bg-white text-[#8D4B00] shadow-xs border border-amber-300' : 'text-stone-600 hover:text-stone-900'} flex items-center justify-center gap-1"
                onclick="window.dubDubStore.updateSubtitleStyle('activeTab', 'bgm')">
                <span class="material-symbols-outlined text-xs">music_note</span> BGM &amp; Ducking
              </button>
            </div>
            <span class="text-[8px] font-mono text-stone-400 bg-stone-100 px-1 py-0.5 rounded border border-stone-200">CapCut Inspector</span>
          </div>

          <!-- Tab Content Scroll Area -->
          <div class="flex-1 min-h-0 overflow-y-auto p-2.5 space-y-2.5">
            ${sub.activeTab === 'text' ? `
              <!-- SECTION A: CAPCUT-STYLE PRESET TEXT BADGES -->
              <div>
                <div class="flex items-center justify-between mb-1">
                  <span class="text-[9px] font-bold uppercase tracking-wider text-stone-500">Preset Text Badges</span>
                  <span class="text-[8px] font-mono text-emerald-700 bg-emerald-50 px-1 rounded font-bold">1-Click Apply</span>
                </div>
                <div class="grid grid-cols-4 gap-1.5">
                  <div 
                    class="p-1 rounded-lg border-2 border-[#8D4B00] bg-amber-50 text-center cursor-pointer shadow-xs"
                    onclick="window.dubDubStore.updateSubtitleStyle('color', '#FBBF24'); window.dubDubStore.updateSubtitleStyle('preset', 'warm_glow');">
                    <span class="text-amber-900 font-extrabold text-[10px] block leading-tight">Warm Glow</span>
                    <span class="text-[7px] text-[#8D4B00] font-mono">Amber Glow</span>
                  </div>
                  <div 
                    class="p-1 rounded-lg border border-stone-200 hover:border-amber-400 text-center cursor-pointer bg-white"
                    onclick="window.dubDubStore.updateSubtitleStyle('color', '#FACC15'); window.dubDubStore.updateSubtitleStyle('preset', 'tiktok_yellow');">
                    <span class="text-stone-950 font-black text-[10px] block bg-yellow-300 rounded px-0.5 leading-tight">TikTok Yellow</span>
                    <span class="text-[7px] text-stone-500 font-mono">High Energy</span>
                  </div>
                  <div 
                    class="p-1 rounded-lg border border-stone-200 hover:border-stone-400 text-center cursor-pointer bg-white"
                    onclick="window.dubDubStore.updateSubtitleStyle('color', '#FFFFFF'); window.dubDubStore.updateSubtitleStyle('preset', 'pill_minimal');">
                    <span class="text-white font-bold text-[9px] block bg-stone-900 rounded px-0.5 leading-tight">Pill Minimal</span>
                    <span class="text-[7px] text-stone-500 font-mono">Clean Box</span>
                  </div>
                  <div 
                    class="p-1 rounded-lg border border-stone-200 hover:border-stone-400 text-center cursor-pointer bg-white"
                    onclick="window.dubDubStore.updateSubtitleStyle('color', '#38BDF8'); window.dubDubStore.updateSubtitleStyle('preset', 'retro_outline');">
                    <span class="text-stone-800 font-extrabold text-[9px] block border border-stone-300 rounded px-0.5 leading-tight shadow-xs">Retro Outline</span>
                    <span class="text-[7px] text-stone-500 font-mono">Contrast</span>
                  </div>
                </div>
              </div>

              <!-- SECTION B: TYPOGRAPHY, FONT SLIDERS & PALETTE -->
              <div class="bg-[#FAF8F5] p-2 rounded-lg border border-stone-200 space-y-1.5">
                <div class="grid grid-cols-2 gap-2">
                  <div>
                    <label class="text-[8px] font-bold uppercase tracking-wider text-stone-500 block mb-0.5">Font Family</label>
                    <select 
                      class="w-full bg-white border border-stone-300 rounded text-[10px] font-bold text-stone-800 py-1 px-1.5 focus:outline-none focus:ring-1 focus:ring-[#8D4B00]"
                      onchange="window.dubDubStore.updateSubtitleStyle('fontFamily', this.value)">
                      <option value="Plus Jakarta Sans" ${sub.fontFamily === 'Plus Jakarta Sans' ? 'selected' : ''}>Plus Jakarta Sans</option>
                      <option value="Montserrat" ${sub.fontFamily === 'Montserrat' ? 'selected' : ''}>Montserrat (Punchy)</option>
                      <option value="Inter" ${sub.fontFamily === 'Inter' ? 'selected' : ''}>Inter (Clean UI)</option>
                      <option value="JetBrains Mono" ${sub.fontFamily === 'JetBrains Mono' ? 'selected' : ''}>JetBrains Mono</option>
                    </select>
                  </div>
                  <div>
                    <div class="flex items-center justify-between text-[8px] font-bold uppercase tracking-wider text-stone-500 mb-0.5">
                      <span>Font Size</span>
                      <span class="font-mono text-[#8D4B00]">${sub.fontSize} px</span>
                    </div>
                    <input 
                      class="w-full accent-[#8D4B00] h-1 bg-stone-200 rounded cursor-pointer mt-1.5" 
                      max="40" 
                      min="12" 
                      type="range" 
                      value="${sub.fontSize}"
                      oninput="window.dubDubStore.updateSubtitleStyle('fontSize', parseInt(this.value))"
                    />
                  </div>
                </div>

                <!-- Color Swatches -->
                <div class="pt-1 border-t border-stone-200/80">
                  <label class="text-[8px] font-bold uppercase tracking-wider text-stone-500 block mb-1">Color Palette</label>
                  <div class="flex items-center gap-2">
                    <button class="w-4 h-4 rounded-full bg-amber-300 ring-2 ring-[#8D4B00] ring-offset-1" onclick="window.dubDubStore.updateSubtitleStyle('color', '#FBBF24')"></button>
                    <button class="w-4 h-4 rounded-full bg-white border border-stone-400" onclick="window.dubDubStore.updateSubtitleStyle('color', '#FFFFFF')"></button>
                    <button class="w-4 h-4 rounded-full bg-yellow-400" onclick="window.dubDubStore.updateSubtitleStyle('color', '#FACC15')"></button>
                    <button class="w-4 h-4 rounded-full bg-emerald-400" onclick="window.dubDubStore.updateSubtitleStyle('color', '#34D399')"></button>
                    <button class="w-4 h-4 rounded-full bg-rose-400" onclick="window.dubDubStore.updateSubtitleStyle('color', '#FB7185')"></button>
                    <button class="w-4 h-4 rounded-full bg-stone-900" onclick="window.dubDubStore.updateSubtitleStyle('color', '#1C1917')"></button>
                  </div>
                </div>
              </div>
            ` : `
              <!-- SECTION C: BGM & DUCKING TAB -->
              <div class="space-y-2">
                <div class="p-2 rounded-lg bg-stone-50 border border-stone-200">
                  <div class="flex items-center justify-between text-xs font-bold text-stone-900 mb-1">
                    <span>Dialogue Priority Ducking</span>
                    <span class="font-mono text-[#8D4B00]">-14 dB</span>
                  </div>
                  <p class="text-[10px] text-stone-500 leading-snug">Automatically drops background music when Alex Carter speaks.</p>
                  <input class="w-full accent-[#8D4B00] h-1 bg-stone-200 rounded mt-2" max="30" min="0" type="range" value="14" />
                </div>

                <div class="p-2 rounded-lg bg-stone-50 border border-stone-200">
                  <div class="flex items-center justify-between text-xs font-bold text-stone-900 mb-1">
                    <span>Background Ambience Volume</span>
                    <span class="font-mono text-stone-700">65%</span>
                  </div>
                  <input class="w-full accent-amber-700 h-1 bg-stone-200 rounded mt-2" max="100" min="0" type="range" value="65" />
                </div>
              </div>
            `}
          </div>
        </aside>
      </div>

      <!-- BOTTOM ROW: CAPCUT MULTI-TRACK NLE TIMELINE DECK (48% Height) -->
      <section class="flex-1 min-h-0 w-full bg-white rounded-xl border border-[#E4DEC3] shadow-xs flex flex-col overflow-hidden">
        <!-- Timeline Controls & Toolbar -->
        <div class="h-8 px-3 border-b border-[#E4DEC3] bg-[#FAF8F5] flex items-center justify-between flex-shrink-0">
          <div class="flex items-center gap-2">
            <div class="flex items-center gap-1 text-stone-700">
              <button 
                class="w-6 h-6 rounded bg-stone-100 hover:bg-stone-200 flex items-center justify-center text-stone-800"
                onclick="window.dubDubStore.togglePlay()">
                <span class="material-symbols-outlined text-sm">${state.playback.isPlaying ? 'pause' : 'play_arrow'}</span>
              </button>
              <button class="w-6 h-6 rounded bg-stone-100 hover:bg-stone-200 flex items-center justify-center text-stone-600" title="Split Clip">
                <span class="material-symbols-outlined text-xs">content_cut</span>
              </button>
              <button class="w-6 h-6 rounded bg-stone-100 hover:bg-stone-200 flex items-center justify-center text-stone-600" title="Delete Selection">
                <span class="material-symbols-outlined text-xs">delete</span>
              </button>
            </div>

            <div class="h-3.5 w-px bg-stone-300"></div>

            <div class="flex items-center gap-1.5 text-[10px] text-stone-600">
              <label class="flex items-center gap-1 cursor-pointer">
                <input checked class="rounded text-[#8D4B00] w-3 h-3 focus:ring-0" type="checkbox" />
                <span>Snap (N)</span>
              </label>
              <label class="flex items-center gap-1 cursor-pointer">
                <input checked class="rounded text-[#8D4B00] w-3 h-3 focus:ring-0" type="checkbox" />
                <span>Auto-Ripple</span>
              </label>
            </div>
          </div>

          <div class="flex items-center gap-3">
            <div class="flex items-center gap-1 font-mono text-[10px] text-stone-600">
              <span class="font-bold text-stone-900">${state.playback.formattedTime}</span>
              <span class="text-stone-300">/</span>
              <span>${p.duration}</span>
            </div>

            <div class="flex items-center gap-1">
              <span class="material-symbols-outlined text-xs text-stone-400">zoom_out</span>
              <input class="w-20 accent-[#8D4B00] h-1 bg-stone-200 rounded" max="200" min="50" type="range" value="100" />
              <span class="material-symbols-outlined text-xs text-stone-400">zoom_in</span>
            </div>
          </div>
        </div>

        <!-- Multi-Track Lanes Container with Playhead -->
        <div class="relative flex-1 min-h-0 overflow-y-auto overflow-x-hidden bg-stone-50 p-2 space-y-1.5">
          <!-- Draggable Red Playhead Line -->
          <div class="absolute top-0 bottom-0 z-30 pointer-events-none flex flex-col items-center" style="left: calc(100px + (100% - 110px) * ${playheadPercent / 100});">
            <div class="w-2.5 h-2.5 bg-[#8D4B00] rotate-45 -mt-1 shadow-xs"></div>
            <div class="w-0.5 flex-1 bg-[#8D4B00] shadow-sm"></div>
          </div>

          <!-- TRACK 1: Video Master (V1) -->
          <div class="h-10 bg-white rounded-lg border border-stone-200 flex items-center shadow-2xs overflow-hidden">
            <div class="w-24 h-full bg-stone-100 border-r border-stone-200 px-2 flex items-center justify-between flex-shrink-0 text-[10px] font-bold text-stone-700">
              <span>V1 Video</span>
              <span class="material-symbols-outlined text-xs text-stone-400">lock</span>
            </div>
            <div class="flex-1 h-full bg-indigo-50/50 p-1 flex items-center gap-1 overflow-hidden">
              <div class="h-full px-3 rounded bg-indigo-100/90 border border-indigo-200 flex items-center text-[9px] font-mono font-bold text-indigo-900 truncate">
                TEDx_Talk_Main_1080p60.mp4 (4K Super-Res Enhanced)
              </div>
            </div>
          </div>

          <!-- TRACK 2: Original Audio Stem (A1) -->
          <div class="h-10 bg-white rounded-lg border border-stone-200 flex items-center shadow-2xs overflow-hidden">
            <div class="w-24 h-full bg-stone-100 border-r border-stone-200 px-2 flex items-center justify-between flex-shrink-0 text-[10px] font-bold text-stone-700">
              <span>A1 Orig Vocals</span>
              <span class="material-symbols-outlined text-xs text-stone-400">volume_up</span>
            </div>
            <div class="flex-1 h-full bg-stone-50 p-1 flex items-center gap-1 overflow-hidden">
              <div class="h-full w-2/3 rounded bg-stone-200 border border-stone-300 px-2 flex items-center justify-between text-[9px] font-mono text-stone-600 truncate">
                <span>Original English Vocals (Muted in Dub)</span>
                <span class="text-[8px] bg-stone-300 px-1 rounded">-24dB</span>
              </div>
            </div>
          </div>

          <!-- TRACK 3: AI Dubbed Audio Stem (A2) -->
          <div class="h-10 bg-white rounded-lg border border-stone-200 flex items-center shadow-2xs overflow-hidden">
            <div class="w-24 h-full bg-amber-50 border-r border-amber-200 px-2 flex items-center justify-between flex-shrink-0 text-[10px] font-bold text-[#8D4B00]">
              <span>A2 AI Dub ★</span>
              <span class="material-symbols-outlined text-xs text-[#8D4B00]">graphic_eq</span>
            </div>
            <div class="flex-1 h-full bg-amber-50/30 p-1 flex items-center gap-1 overflow-hidden">
              <div class="h-full w-3/4 rounded bg-amber-200/80 border border-amber-400/80 px-2 flex items-center justify-between text-[9px] font-mono font-bold text-amber-950 truncate shadow-2xs">
                <span>Spanish Neural Dub (Alex Carter Clone • Lip-Mesh Synced)</span>
                <span class="text-[8px] bg-amber-400 text-amber-950 px-1 rounded font-mono">0dB Active</span>
              </div>
            </div>
          </div>

          <!-- TRACK 4: Background Music & Sound Effects (A3) -->
          <div class="h-10 bg-white rounded-lg border border-stone-200 flex items-center shadow-2xs overflow-hidden">
            <div class="w-24 h-full bg-stone-100 border-r border-stone-200 px-2 flex items-center justify-between flex-shrink-0 text-[10px] font-bold text-stone-700">
              <span>A3 BGM Stem</span>
              <span class="material-symbols-outlined text-xs text-stone-400">music_note</span>
            </div>
            <div class="flex-1 h-full bg-emerald-50/30 p-1 flex items-center gap-1 overflow-hidden">
              <div class="h-full w-full rounded bg-emerald-100 border border-emerald-300 px-2 flex items-center justify-between text-[9px] font-mono text-emerald-900 truncate">
                <span>Original BGM &amp; Keynote Ambience (Auto-Ducked -14dB during speech)</span>
                <span class="text-[8px] bg-emerald-200 px-1 rounded">Ducked</span>
              </div>
            </div>
          </div>

          <!-- TRACK 5: Burned Subtitle & OCR Cues (T1) -->
          <div class="h-10 bg-white rounded-lg border border-stone-200 flex items-center shadow-2xs overflow-hidden">
            <div class="w-24 h-full bg-stone-100 border-r border-stone-200 px-2 flex items-center justify-between flex-shrink-0 text-[10px] font-bold text-stone-700">
              <span>T1 Subtitles</span>
              <span class="material-symbols-outlined text-xs text-stone-400">subtitles</span>
            </div>
            <div class="flex-1 h-full bg-amber-50/20 p-1 flex items-center gap-1 overflow-hidden">
              <div class="h-full w-1/4 rounded bg-amber-300/80 border border-amber-400 px-2 flex items-center text-[9px] font-mono font-bold text-amber-950 truncate shadow-2xs">
                Cue #01 (ES Sub)
              </div>
              <div class="h-full w-1/4 rounded bg-amber-400 border border-amber-500 px-2 flex items-center text-[9px] font-mono font-bold text-amber-950 truncate shadow-2xs">
                Cue #02 (OCR Target)
              </div>
              <div class="h-full w-1/4 rounded bg-amber-300/80 border border-amber-400 px-2 flex items-center text-[9px] font-mono font-bold text-amber-950 truncate shadow-2xs">
                Cue #03 (Elena)
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  `;
}
