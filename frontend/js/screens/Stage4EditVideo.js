/**
 * Stage 4: Lightweight Video Editing Studio (CapCut Style)
 * Provides video preview with live subtitle styling, multi-track timeline,
 * independent audio source mixing (original, dubbed, BGM), and thumbnail management.
 */

import { renderVideoPlayer } from '../components/VideoPlayer.js';

const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
})[c]);

const time = seconds => {
  const value = Math.max(0, Number(seconds) || 0);
  const m = Math.floor(value / 60);
  const s = Math.floor(value % 60);
  const ms = Math.round((value % 1) * 1000);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms).padStart(3, '0')}`;
};

const audioSlider = (label, key, value, icon, muted = false) => `
  <div class="rounded-xl border border-stone-200/80 bg-[#FAF9F6] p-3 shadow-2xs">
    <div class="mb-2 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <div class="w-6 h-6 rounded-md ${muted ? 'bg-stone-200 text-stone-500' : 'bg-amber-100 text-[#8D4B00]'} flex items-center justify-center">
          <span class="material-symbols-outlined text-sm">${icon}</span>
        </div>
        <span class="text-xs font-bold text-stone-800">${label}</span>
      </div>
      <div class="flex items-center gap-1.5">
        <button type="button" data-action="toggle-mute-${key}" class="px-1.5 py-0.5 rounded text-[10px] font-semibold ${muted ? 'bg-stone-300 text-stone-700' : 'bg-stone-200 hover:bg-stone-300 text-stone-700'}"
          title="${muted ? 'Unmute' : 'Mute'}"
          onclick="window.dubDubStore.toggleAudioMute('${key}')">
          <span class="material-symbols-outlined text-xs align-middle">${muted ? 'volume_off' : 'volume_up'}</span>
        </button>
        <output class="font-mono text-xs font-bold ${muted ? 'text-stone-400 line-through' : 'text-[#8D4B00]'}">${value}%</output>
      </div>
    </div>
    <input data-mix-slider="${key}" class="w-full accent-[#8D4B00] cursor-pointer h-1.5 bg-stone-200 rounded-lg appearance-none" type="range" min="0" max="150" value="${value}"
      oninput="this.closest('div').querySelector('output').textContent=this.value+'%'; window.dubDubStore.updateAudioMix('${key}', Number(this.value), false)"
      onchange="window.dubDubStore.updateAudioMix('${key}', Number(this.value))" />
  </div>`;

export function renderStage4EditVideo(state) {
  const edit = state.editVideo;
  const style = state.subtitleStyles;
  const totalDuration = Math.max(1, state.project.durationSec || (state.segments.length ? state.segments[state.segments.length - 1].endSec : 60));
  const activeTab = edit.activeTab || 'audio';

  // Active segment for editing
  const active = state.segments.find(seg => String(seg.id) === String(state.activeSegmentId)) || state.segments[0] || {};
  const activeIndex = state.segments.findIndex(seg => String(seg.id) === String(active.id));

  // Default clean subtitle styling (White text, black outline, subtle shadow, centered near bottom)
  const liveStyle = `color:${style.color || '#FFFFFF'};font-family:${style.fontFamily || 'Arial'};font-size:${style.fontSize || 22}px;-webkit-text-stroke:${style.outlineWidth ?? 2}px ${style.outlineColor || '#000000'};paint-order:stroke fill;text-shadow:0 ${style.shadowSize ?? 2}px ${(style.shadowSize ?? 2) * 2}px ${style.shadowColor || 'rgba(0,0,0,0.75)'};text-align:center;`;

  // Audio mute states
  const isOrigMuted = (Number(edit.audioMix.original) || 0) === 0;
  const isDubbedMuted = (Number(edit.audioMix.dubbed) || 0) === 0;
  const isBgmMuted = (Number(edit.audioMix.background) || 0) === 0;

  return `
    <div data-stage4-studio class="flex-1 min-h-0 w-full p-2.5 flex flex-col gap-2.5 overflow-hidden bg-[#F4F1EA]">
      <!-- Hidden BGM Audio element synchronized with video playback -->
      <audio id="stage4-bgm-preview" src="${esc(edit.backgroundAudio?.previewUrl || '')}" preload="auto" loop class="hidden"></audio>

      <!-- UPPER DECK: Video Preview (Left) + Contextual Inspector / Settings Panel (Right) -->
      <div class="flex-1 min-h-0 grid grid-cols-12 gap-2.5 overflow-hidden">
        <!-- 1. Video Preview Area (7 Cols) -->
        <section class="col-span-12 lg:col-span-7 xl:col-span-8 min-h-0 flex flex-col rounded-xl overflow-hidden border border-[#E2DDD3] bg-white shadow-xs">
          ${renderVideoPlayer(state, { title: 'Studio Preview', subtitleVariant: 'capcut' })}
          <style>[data-canvas-subtitle]{${liveStyle}}</style>
        </section>

        <!-- 2. Settings Panel / Inspector (5 Cols) -->
        <aside class="col-span-12 lg:col-span-5 xl:col-span-4 min-h-0 rounded-xl border border-[#E2DDD3] bg-white flex flex-col overflow-hidden shadow-xs">
          <!-- Inspector Header Tabs -->
          <header class="h-10 px-3 border-b border-stone-200 bg-[#FAF9F6] flex items-center justify-between flex-shrink-0">
            <div class="flex items-center gap-1">
              <button type="button" data-inspector-tab="audio" class="px-2.5 py-1 rounded-lg text-xs font-bold transition-colors flex items-center gap-1 ${activeTab === 'audio' ? 'bg-[#8D4B00] text-white shadow-2xs' : 'text-stone-600 hover:bg-stone-100'}"
                onclick="window.dubDubStore.setStage4InspectorTab('audio')">
                <span class="material-symbols-outlined text-sm">volume_up</span>
                <span>Audio Mix</span>
              </button>
              <button type="button" data-inspector-tab="subtitles" class="px-2.5 py-1 rounded-lg text-xs font-bold transition-colors flex items-center gap-1 ${activeTab === 'subtitles' ? 'bg-[#8D4B00] text-white shadow-2xs' : 'text-stone-600 hover:bg-stone-100'}"
                onclick="window.dubDubStore.setStage4InspectorTab('subtitles')">
                <span class="material-symbols-outlined text-sm">subtitles</span>
                <span>Subtitles</span>
              </button>
              <button type="button" data-inspector-tab="thumbnail" class="px-2.5 py-1 rounded-lg text-xs font-bold transition-colors flex items-center gap-1 ${activeTab === 'thumbnail' ? 'bg-[#8D4B00] text-white shadow-2xs' : 'text-stone-600 hover:bg-stone-100'}"
                onclick="window.dubDubStore.setStage4InspectorTab('thumbnail')">
                <span class="material-symbols-outlined text-sm">image</span>
                <span>Thumbnail</span>
              </button>
            </div>
            <button type="button" data-action="export-edited-video" class="px-2.5 py-1 rounded-lg bg-[#8D4B00] hover:bg-[#743d00] text-white text-[11px] font-bold shadow-xs flex items-center gap-1 transition-colors"
              onclick="window.dubDubStore.exportEditedVideo()">
              <span class="material-symbols-outlined text-xs">movie_creation</span>
              <span>Export</span>
            </button>
          </header>

          <!-- Inspector Content Body -->
          <div class="flex-1 overflow-y-auto p-3.5 space-y-4">
            ${activeTab === 'audio' ? `
              <!-- TAB 1: AUDIO MIX -->
              <div class="space-y-3.5">
                <div>
                  <h3 class="text-xs font-bold text-stone-900">Audio Sources</h3>
                  <p class="text-[11px] text-stone-500">Balance original dialogue, dubbed TTS voiceover, and background music.</p>
                </div>

                <!-- Three Clearly Separated Audio Sources -->
                <div class="space-y-2.5">
                  ${audioSlider('Original Video Audio', 'original', edit.audioMix.original, 'movie', isOrigMuted)}
                  ${audioSlider('Dubbed TTS Audio', 'dubbed', edit.audioMix.dubbed, 'record_voice_over', isDubbedMuted)}
                  ${audioSlider('Background Music', 'background', edit.audioMix.background, 'music_note', isBgmMuted)}
                </div>

                <!-- Background Music File Manager -->
                <div class="pt-2 border-t border-stone-200">
                  <div class="flex items-center justify-between mb-2">
                    <span class="text-xs font-bold text-stone-800">Background Music Track</span>
                    ${edit.backgroundAudio ? `
                      <button type="button" class="text-[10px] font-semibold text-red-600 hover:text-red-700" onclick="window.dubDubStore.removeBackgroundAudio()">
                        Remove BGM
                      </button>
                    ` : ''}
                  </div>

                  <input id="stage4-background-input" type="file" accept="audio/*" class="hidden" onchange="window.dubDubStore.selectBackgroundAudio(this.files[0])" />

                  ${edit.backgroundAudio ? `
                    <div class="rounded-xl border border-amber-200 bg-amber-50/60 p-2.5 flex items-center justify-between gap-2">
                      <div class="flex items-center gap-2 min-w-0">
                        <div class="w-8 h-8 rounded-lg bg-[#8D4B00] text-amber-100 flex items-center justify-center flex-shrink-0">
                          <span class="material-symbols-outlined text-base">music_note</span>
                        </div>
                        <div class="min-w-0">
                          <div class="text-xs font-bold text-stone-900 truncate">${esc(edit.backgroundAudio.name)}</div>
                          <div class="text-[10px] text-stone-500">Synchronized with master playhead</div>
                        </div>
                      </div>
                      <button type="button" class="px-2 py-1 rounded-lg border border-stone-300 bg-white hover:bg-stone-50 text-[11px] font-semibold text-stone-700 flex-shrink-0"
                        onclick="document.getElementById('stage4-background-input').click()">
                        Replace
                      </button>
                    </div>
                  ` : `
                    <button type="button" class="w-full rounded-xl border-2 border-dashed border-stone-300 hover:border-[#8D4B00] p-3 text-center transition-colors group cursor-pointer bg-white"
                      onclick="document.getElementById('stage4-background-input').click()">
                      <span class="material-symbols-outlined text-xl text-stone-400 group-hover:text-[#8D4B00] block mb-0.5">library_music</span>
                      <span class="block text-xs font-bold text-stone-700 group-hover:text-[#8D4B00]">Add Background Music</span>
                      <span class="block text-[10px] text-stone-400">MP3, WAV, AAC, M4A, FLAC, OGG</span>
                    </button>
                  `}
                </div>
              </div>
            ` : activeTab === 'subtitles' ? `
              <!-- TAB 2: SUBTITLES & STYLING -->
              <div class="space-y-3.5">
                <div>
                  <h3 class="text-xs font-bold text-stone-900">Subtitle Appearance</h3>
                  <p class="text-[11px] text-stone-500">White text with black outline & shadow centered at bottom.</p>
                </div>

                <!-- Font Size Adjustment Slider & Number Input -->
                <div class="rounded-xl border border-stone-200/80 bg-[#FAF9F6] p-3 space-y-2">
                  <div class="flex items-center justify-between text-xs font-bold text-stone-800">
                    <span class="flex items-center gap-1">
                      <span class="material-symbols-outlined text-sm text-[#8D4B00]">format_size</span>
                      <span>Font Size</span>
                    </span>
                    <div class="flex items-center gap-1.5">
                      <input data-action="update-font-size-input" type="number" min="8" max="64" step="1" value="${style.fontSize || 22}"
                        class="w-14 rounded border border-stone-300 px-1.5 py-0.5 font-mono text-xs text-right font-bold text-[#8D4B00] bg-white focus:border-[#8D4B00] focus:ring-1 focus:ring-[#8D4B00] focus:outline-none"
                        oninput="const val=Math.max(8, Math.min(64, Number(this.value) || 22)); const sl=this.closest('div.space-y-2').querySelector('[data-action=\\'update-font-size\\']'); if (sl) sl.value=val; window.dubDubStore.updateSubtitleStyle('fontSize', val, false);"
                        onchange="const val=Math.max(8, Math.min(64, Number(this.value) || 22)); this.value=val; window.dubDubStore.updateSubtitleStyle('fontSize', val, true);" />
                      <span class="text-xs font-mono text-stone-500 font-bold">px</span>
                    </div>
                  </div>
                  <input data-action="update-font-size" class="w-full accent-[#8D4B00] cursor-pointer h-1.5 bg-stone-200 rounded-lg appearance-none"
                    type="range" min="8" max="64" step="1" value="${style.fontSize || 22}"
                    oninput="const num=this.closest('div.space-y-2').querySelector('[data-action=\\'update-font-size-input\\']'); if (num) num.value=this.value; window.dubDubStore.updateSubtitleStyle('fontSize', Number(this.value), false);"
                    onchange="window.dubDubStore.updateSubtitleStyle('fontSize', Number(this.value), true)" />
                </div>

                <!-- Font Family & Outline & Shadow Controls -->
                <div class="grid grid-cols-2 gap-2 text-[11px]">
                  <label class="block space-y-1">
                    <span class="font-semibold text-stone-600">Font Family</span>
                    <select class="w-full rounded-lg border border-stone-300 bg-white px-2 py-1 text-xs" onchange="window.dubDubStore.updateSubtitleStyle('fontFamily', this.value)">
                      ${['Arial', 'Inter', 'Montserrat', 'Plus Jakarta Sans', 'Roboto'].map(f => `
                        <option value="${f}" ${style.fontFamily === f ? 'selected' : ''}>${f}</option>
                      `).join('')}
                    </select>
                  </label>

                  <label class="block space-y-1">
                    <span class="font-semibold text-stone-600">Text Color</span>
                    <div class="flex items-center gap-1.5 h-[29px] px-2 rounded-lg border border-stone-300 bg-white">
                      <input type="color" value="${style.color || '#FFFFFF'}" class="w-5 h-5 rounded cursor-pointer border-0" onchange="window.dubDubStore.updateSubtitleStyle('color', this.value)" />
                      <span class="font-mono text-[10px] text-stone-600">${style.color || '#FFFFFF'}</span>
                    </div>
                  </label>

                  <label class="block space-y-1">
                    <span class="font-semibold text-stone-600 flex justify-between">Outline <span>${style.outlineWidth ?? 2}px</span></span>
                    <input type="range" min="0" max="5" value="${style.outlineWidth ?? 2}" class="w-full accent-[#8D4B00] cursor-pointer h-1.5 bg-stone-200 rounded-lg"
                      oninput="window.dubDubStore.updateSubtitleStyle('outlineWidth', Number(this.value))" />
                  </label>

                  <label class="block space-y-1">
                    <span class="font-semibold text-stone-600 flex justify-between">Shadow <span>${style.shadowSize ?? 2}px</span></span>
                    <input type="range" min="0" max="6" value="${style.shadowSize ?? 2}" class="w-full accent-[#8D4B00] cursor-pointer h-1.5 bg-stone-200 rounded-lg"
                      oninput="window.dubDubStore.updateSubtitleStyle('shadowSize', Number(this.value))" />
                  </label>
                </div>

                <!-- Selected Subtitle Segment Editor -->
                <div class="pt-2 border-t border-stone-200 space-y-2">
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-1.5">
                      <span class="px-2 py-0.5 rounded-full bg-[#8D4B00] text-white font-mono font-bold text-[10px]">
                        Cue #${String(active?.id ?? 1).padStart(2, '0')}
                      </span>
                      <span class="text-xs font-bold text-stone-800">Edit Selected Subtitle</span>
                    </div>
                    <div class="flex items-center gap-1 text-[10px]">
                      <button type="button" class="px-1.5 py-0.5 rounded border border-stone-300 hover:bg-stone-100 disabled:opacity-40"
                        ${activeIndex <= 0 ? 'disabled' : ''}
                        onclick="window.dubDubStore.seekAndPlay(${state.segments[activeIndex - 1]?.startSec || 0}, '${state.segments[activeIndex - 1]?.id}');">
                        &larr; Prev
                      </button>
                      <button type="button" class="px-1.5 py-0.5 rounded border border-stone-300 hover:bg-stone-100 disabled:opacity-40"
                        ${activeIndex >= state.segments.length - 1 ? 'disabled' : ''}
                        onclick="window.dubDubStore.seekAndPlay(${state.segments[activeIndex + 1]?.startSec || 0}, '${state.segments[activeIndex + 1]?.id}');">
                        Next &rarr;
                      </button>
                    </div>
                  </div>

                  <div class="flex items-center gap-2 text-[10px] font-mono text-stone-500">
                    <span>${time(active?.startSec)} &rarr; ${time(active?.endSec)}</span>
                    <label class="flex items-center gap-1">Start:
                      <input type="number" step="0.001" min="0" value="${Number(active?.startSec) || 0}" class="w-14 rounded border border-stone-300 px-1 py-0.5 font-mono text-[10px]"
                        onchange="window.dubDubStore.updateStage4Timing('${esc(active?.id)}', 'startSec', this.value)" />
                    </label>
                    <label class="flex items-center gap-1">End:
                      <input type="number" step="0.001" min="0" value="${Number(active?.endSec) || 0}" class="w-14 rounded border border-stone-300 px-1 py-0.5 font-mono text-[10px]"
                        onchange="window.dubDubStore.updateStage4Timing('${esc(active?.id)}', 'endSec', this.value)" />
                    </label>
                  </div>

                  <textarea data-stage4-subtitle="${esc(active?.id)}" data-segment-input="stage4-${esc(active?.id)}" class="w-full min-h-[70px] resize-none rounded-lg border border-stone-300 bg-white p-2 text-xs leading-relaxed focus:border-[#8D4B00] focus:ring-1 focus:ring-[#8D4B00] focus:outline-none"
                    placeholder="Enter translated subtitle text..."
                    oninput="window.dubDubStore.updateStage4Subtitle('${esc(active?.id)}', this.value)"
                    onblur="window.dubDubStore.updateStage4Subtitle('${esc(active?.id)}', this.value, true)">${esc(active?.targetText || active?.sourceText || active?.text || '')}</textarea>
                </div>
              </div>
            ` : `
              <!-- TAB 3: THUMBNAIL -->
              <div class="space-y-3.5">
                <div>
                  <h3 class="text-xs font-bold text-stone-900">Video Thumbnail</h3>
                  <p class="text-[11px] text-stone-500">Set the cover image embedded in the exported video file.</p>
                </div>

                <input id="stage4-thumbnail-input" type="file" accept="image/png,image/jpeg,image/webp" class="hidden" onchange="window.dubDubStore.selectThumbnail(this.files[0])" />

                ${edit.thumbnail?.previewUrl ? `
                  <div class="space-y-2">
                    <div data-thumbnail-preview class="relative rounded-xl overflow-hidden border border-stone-300 bg-black aspect-video group">
                      <img src="${esc(edit.thumbnail.previewUrl)}" alt="Selected video thumbnail" class="w-full h-full object-cover" />
                      <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                        <button type="button" class="px-2.5 py-1 rounded-lg bg-white/90 hover:bg-white text-stone-900 text-xs font-bold shadow-sm"
                          onclick="document.getElementById('stage4-thumbnail-input').click()">
                          Change Image
                        </button>
                        <button type="button" class="px-2.5 py-1 rounded-lg bg-red-600 hover:bg-red-700 text-white text-xs font-bold shadow-sm"
                          onclick="window.dubDubStore.removeThumbnail()">
                          Remove
                        </button>
                      </div>
                    </div>
                    <div class="flex items-center justify-between text-xs">
                      <span class="font-medium text-stone-700 truncate max-w-[200px]">${esc(edit.thumbnail.name)}</span>
                      <button type="button" class="text-[11px] font-semibold text-red-600 hover:text-red-700" onclick="window.dubDubStore.removeThumbnail()">
                        Remove
                      </button>
                    </div>
                  </div>
                ` : `
                  <div class="rounded-xl border-2 border-dashed border-stone-300 p-6 text-center bg-white space-y-2">
                    <div class="w-10 h-10 rounded-full bg-amber-50 text-[#8D4B00] flex items-center justify-center mx-auto">
                      <span class="material-symbols-outlined text-xl">add_photo_alternate</span>
                    </div>
                    <div>
                      <span class="block text-xs font-bold text-stone-800">No Custom Thumbnail</span>
                      <span class="block text-[11px] text-stone-500">First frame of the video will be used by default</span>
                    </div>
                    <button type="button" class="px-3.5 py-1.5 rounded-lg bg-[#8D4B00] hover:bg-[#743d00] text-white font-bold text-xs shadow-xs transition-colors"
                      onclick="document.getElementById('stage4-thumbnail-input').click()">
                      Upload Thumbnail
                    </button>
                    <p class="text-[10px] text-stone-400">PNG, JPG, JPEG, WEBP (16:9 recommended)</p>
                  </div>
                `}
              </div>
            `}

            ${edit.error ? `<p class="rounded-lg bg-red-50 p-2 text-xs text-red-700 border border-red-200">${esc(edit.error)}</p>` : ''}
          </div>
        </aside>
      </div>

      <!-- LOWER DECK: Multi-Track Timeline Editing Studio (CapCut Style) -->
      <section data-timeline-container class="h-[210px] flex-shrink-0 rounded-xl border border-[#E2DDD3] bg-white flex flex-col overflow-hidden shadow-xs">
        <!-- Timeline Toolbar -->
        <div class="h-9 px-3 border-b border-stone-200 bg-[#FAF9F6] flex items-center justify-between flex-shrink-0">
          <div class="flex items-center gap-3">
            <button type="button" class="w-6 h-6 rounded-md bg-[#8D4B00] text-white flex items-center justify-center hover:bg-[#743d00] transition-colors shadow-2xs"
              onclick="window.dubDubStore.togglePlay()">
              <span data-preview-action-icon class="material-symbols-outlined text-base">play_arrow</span>
            </button>
            <div class="font-mono text-xs font-bold text-stone-800">
              <span data-playhead-timecode>${state.playback.formattedTime}</span>
              <span class="text-stone-400">/</span>
              <span class="text-stone-500">${state.project.duration}</span>
            </div>
            <button type="button" class="text-[10px] font-semibold text-stone-600 hover:text-stone-900 border border-stone-200 bg-white px-2 py-0.5 rounded shadow-2xs"
              onclick="window.dubDubStore.seekPreview(0)">
              Seek Start
            </button>
          </div>

          <div class="flex items-center gap-3 text-[11px] text-stone-500">
            <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-amber-500"></span> Subtitle Cues</span>
            <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-indigo-500"></span> Dubbed TTS</span>
            <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-emerald-500"></span> BGM</span>
          </div>
        </div>

        <!-- Tracks Container (Left: Track Headers, Right: Interactive Multi-Track Lanes) -->
        <div class="flex-1 min-h-0 flex overflow-hidden">
          <!-- Track Headers Column (130px) -->
          <div class="w-36 flex-shrink-0 border-r border-stone-200 bg-[#FAF9F6] flex flex-col text-[11px] font-semibold text-stone-700 divide-y divide-stone-200 select-none">
            <!-- Time Ruler Header -->
            <div class="h-6 px-2 flex items-center text-[10px] text-stone-400 font-mono">TIMELINE</div>
            <!-- Video Track Header -->
            <div class="h-8 px-2 flex items-center justify-between hover:bg-stone-100 cursor-pointer" onclick="window.dubDubStore.setStage4InspectorTab('thumbnail')">
              <span class="flex items-center gap-1 truncate"><span class="material-symbols-outlined text-xs text-stone-500">movie</span>Video</span>
              <span class="text-[9px] font-mono text-stone-400">16:9</span>
            </div>
            <!-- Subtitle Track Header -->
            <div class="h-8 px-2 flex items-center justify-between hover:bg-stone-100 cursor-pointer" onclick="window.dubDubStore.setStage4InspectorTab('subtitles')">
              <span class="flex items-center gap-1 truncate"><span class="material-symbols-outlined text-xs text-amber-600">subtitles</span>Subs</span>
              <span class="text-[9px] font-mono px-1 rounded bg-amber-100 text-[#8D4B00]">${state.segments.length}</span>
            </div>
            <!-- Dubbed TTS Track Header -->
            <div class="h-8 px-2 flex items-center justify-between hover:bg-stone-100 cursor-pointer" onclick="window.dubDubStore.setStage4InspectorTab('audio')">
              <span class="flex items-center gap-1 truncate"><span class="material-symbols-outlined text-xs text-indigo-600">record_voice_over</span>Dubbed</span>
              <span class="text-[9px] font-mono text-stone-500">${edit.audioMix.dubbed}%</span>
            </div>
            <!-- Background Music Track Header -->
            <div class="h-8 px-2 flex items-center justify-between hover:bg-stone-100 cursor-pointer" onclick="window.dubDubStore.setStage4InspectorTab('audio')">
              <span class="flex items-center gap-1 truncate"><span class="material-symbols-outlined text-xs text-emerald-600">music_note</span>BGM</span>
              <span class="text-[9px] font-mono text-stone-500">${edit.audioMix.background}%</span>
            </div>
          </div>

          <!-- Multi-Track Lanes & Scrubber Area -->
          <div class="flex-1 min-h-0 relative overflow-x-auto overflow-y-hidden bg-[#F8F7F4] select-none"
            onclick="const r=this.getBoundingClientRect(); const p=Math.max(0, Math.min(1, (event.clientX-r.left)/r.width)); window.dubDubStore.seekPreview(p * ${totalDuration});"
            onpointerdown="const r=this.getBoundingClientRect(); const p=Math.max(0, Math.min(1, (event.clientX-r.left)/r.width)); window.dubDubStore.seekPreview(p * ${totalDuration}); this._scrubbing=true;"
            onpointermove="if (this._scrubbing && event.buttons > 0) { const r=this.getBoundingClientRect(); const p=Math.max(0, Math.min(1, (event.clientX-r.left)/r.width)); window.dubDubStore.seekPreview(p * ${totalDuration}); }"
            onpointerup="this._scrubbing=false;">
            
            <!-- Interactive Playhead Needle across all tracks -->
            <div data-timeline-playhead class="absolute top-0 bottom-0 w-0.5 bg-amber-500 z-30 pointer-events-none transition-all duration-75" style="left: ${(state.playback.currentTime / totalDuration) * 100}%;">
              <div class="w-3 h-3 bg-amber-500 rounded-b -ml-1.25 shadow-md flex items-center justify-center">
                <div class="w-1 h-1 bg-white rounded-full"></div>
              </div>
            </div>

            <!-- Time Ruler Lane -->
            <div class="h-6 border-b border-stone-200 bg-[#FAF9F6] relative text-[9px] font-mono text-stone-400 flex items-center px-1 pointer-events-none">
              <div class="absolute left-0">00:00.000</div>
              <div class="absolute left-1/4 -translate-x-1/2">${time(totalDuration * 0.25)}</div>
              <div class="absolute left-2/4 -translate-x-1/2">${time(totalDuration * 0.50)}</div>
              <div class="absolute left-3/4 -translate-x-1/2">${time(totalDuration * 0.75)}</div>
              <div class="absolute right-1">${time(totalDuration)}</div>
            </div>

            <!-- Track 1: Video Track Lane -->
            <div data-timeline-track="video" class="h-8 border-b border-stone-200/80 relative p-0.5">
              <div class="h-full rounded-md bg-stone-800 text-stone-200 px-2 flex items-center justify-between text-[10px] font-mono border border-stone-700 shadow-2xs">
                <span class="flex items-center gap-1 truncate"><span class="material-symbols-outlined text-xs">video_file</span>${esc(state.project.title || 'Source Video')}</span>
                <span class="text-[9px] text-stone-400">${state.project.resolution}</span>
              </div>
            </div>

            <!-- Track 2: Subtitles Track Lane -->
            <div data-timeline-track="subtitles" class="h-8 border-b border-stone-200/80 relative p-0.5">
              ${state.segments.map(seg => {
                const left = (seg.startSec / totalDuration) * 100;
                const width = Math.max(0.8, ((seg.endSec - seg.startSec) / totalDuration) * 100);
                const isSelected = String(seg.id) === String(active?.id);
                return `
                  <div data-segment-card="${esc(seg.id)}" data-timeline-cue="${esc(seg.id)}"
                    class="absolute top-0.5 bottom-0.5 rounded px-1.5 flex items-center overflow-hidden cursor-pointer transition-all border ${isSelected ? 'bg-amber-400 text-stone-950 font-bold border-[#8D4B00] shadow-xs z-10' : 'bg-amber-100/90 text-amber-950 border-amber-300 hover:bg-amber-200'}"
                    style="left: ${left}%; width: ${width}%;"
                    title="${time(seg.startSec)} → ${time(seg.endSec)}: ${esc(seg.targetText || seg.sourceText || '')}"
                    onclick="event.stopPropagation(); window.dubDubStore.seekAndPlay(${Number(seg.startSec) || 0}, '${esc(seg.id)}'); window.dubDubStore.setStage4InspectorTab('subtitles');">
                    <span class="text-[9px] truncate font-medium">${esc(seg.targetText || seg.sourceText || `Cue #${seg.id}`)}</span>
                  </div>
                `;
              }).join('')}
            </div>

            <!-- Track 3: Dubbed TTS Audio Track Lane -->
            <div data-timeline-track="dubbing" class="h-8 border-b border-stone-200/80 relative p-0.5">
              ${state.segments.map(seg => {
                const left = (seg.startSec / totalDuration) * 100;
                const width = Math.max(0.8, ((seg.endSec - seg.startSec) / totalDuration) * 100);
                return `
                  <div class="absolute top-0.5 bottom-0.5 rounded px-1 flex items-center overflow-hidden bg-indigo-100 border border-indigo-300 text-indigo-900 cursor-pointer hover:bg-indigo-200"
                    style="left: ${left}%; width: ${width}%;"
                    title="Dubbed TTS Voice: ${esc(seg.voiceOverride || 'Speaker Default')}"
                    onclick="event.stopPropagation(); window.dubDubStore.seekAndPlay(${Number(seg.startSec) || 0}, '${esc(seg.id)}'); window.dubDubStore.setStage4InspectorTab('audio');">
                    <span class="material-symbols-outlined text-[10px] mr-0.5 text-indigo-700">graphic_eq</span>
                    <span class="text-[9px] truncate font-mono">${esc(seg.voiceOverride || seg.speakerName || 'Voice')}</span>
                  </div>
                `;
              }).join('')}
            </div>

            <!-- Track 4: Background Music Track Lane -->
            <div data-timeline-track="bgm" class="h-8 relative p-0.5">
              ${edit.backgroundAudio ? `
                <div class="h-full rounded-md bg-emerald-100 border border-emerald-300 text-emerald-950 px-2 flex items-center justify-between text-[10px] cursor-pointer hover:bg-emerald-200"
                  onclick="event.stopPropagation(); window.dubDubStore.setStage4InspectorTab('audio');">
                  <span class="flex items-center gap-1 truncate font-medium"><span class="material-symbols-outlined text-xs text-emerald-700">music_note</span>${esc(edit.backgroundAudio.name)}</span>
                  <span class="text-[9px] font-mono text-emerald-800">${edit.audioMix.background}%</span>
                </div>
              ` : `
                <button type="button" class="w-full h-full rounded border border-dashed border-stone-300 hover:border-[#8D4B00] text-stone-400 hover:text-[#8D4B00] flex items-center justify-center gap-1 text-[10px] font-medium bg-white/50"
                  onclick="event.stopPropagation(); document.getElementById('stage4-background-input').click();">
                  <span class="material-symbols-outlined text-xs">add</span> Add BGM track
                </button>
              `}
            </div>
          </div>
        </div>
      </section>
    </div>
  `;
}
