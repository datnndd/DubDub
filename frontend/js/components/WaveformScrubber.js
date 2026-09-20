/**
 * Reusable WaveformScrubber Component
 * Waveform audio track and transport deck.
 */

export function renderWaveformScrubber(state) {
  const percent = Math.min(100, Math.max(0, (state.playback.currentTime / state.project.durationSec) * 100));
  const isPlaying = state.playback.isPlaying;

  return `
    <div class="p-2 bg-[#FAF9F6] border-t border-[#E7E4DC] flex flex-col gap-1 flex-shrink-0">
      <!-- Waveform Audio Stem Track with Scrub Marker -->
      <div 
        class="relative w-full h-5 flex items-center cursor-pointer group/scrub" 
        onclick="const rect = this.getBoundingClientRect(); const p = (event.clientX - rect.left) / rect.width; window.dubDubStore.setPlaybackTime(p * ${state.project.durationSec});"
      >
        <svg class="w-full h-4 text-amber-200/90" fill="currentColor" preserveAspectRatio="none" viewBox="0 0 300 20">
          <rect height="6" rx="1" width="2" x="0" y="7"></rect><rect height="10" rx="1" width="2" x="4" y="5"></rect>
          <rect height="14" rx="1" width="2" x="8" y="3"></rect><rect height="5" rx="1" width="2" x="12" y="8"></rect>
          <rect height="16" rx="1" width="2" x="16" y="2"></rect><rect height="12" rx="1" width="2" x="20" y="4"></rect>
          <rect height="18" rx="1" width="2" x="24" y="1"></rect><rect height="8" rx="1" width="2" x="28" y="6"></rect>
          <rect height="15" rx="1" width="2" x="32" y="3"></rect><rect height="7" rx="1" width="2" x="36" y="7"></rect>
          <rect height="12" rx="1" width="2" x="40" y="4"></rect><rect height="17" rx="1" width="2" x="44" y="2"></rect>
          <rect height="10" rx="1" width="2" x="48" y="5"></rect><rect height="15" rx="1" width="2" x="52" y="3"></rect>
          <rect height="7" rx="1" width="2" x="56" y="7"></rect><rect height="14" rx="1" width="2" x="60" y="3"></rect>
          <rect height="9" rx="1" width="2" x="64" y="6"></rect><rect height="18" rx="1" width="2" x="68" y="1"></rect>
          <rect height="12" rx="1" width="2" x="72" y="4"></rect><rect height="7" rx="1" width="2" x="76" y="7"></rect>
          <rect height="16" rx="1" width="2" x="80" y="2"></rect><rect height="11" rx="1" width="2" x="84" y="5"></rect>
          <rect height="17" rx="1" width="2" x="88" y="2"></rect><rect height="9" rx="1" width="2" x="92" y="6"></rect>
          <rect height="14" rx="1" width="2" x="96" y="3"></rect><rect height="7" rx="1" width="2" x="100" y="7"></rect>
          <rect height="16" rx="1" width="2" x="104" y="2"></rect><rect height="11" rx="1" width="2" x="108" y="5"></rect>
          <rect height="18" rx="1" width="2" x="112" y="1"></rect><rect height="13" rx="1" width="2" x="116" y="4"></rect>
          <rect height="7" rx="1" width="2" x="120" y="7"></rect><rect height="16" rx="1" width="2" x="124" y="2"></rect>
          <rect height="10" rx="1" width="2" x="128" y="5"></rect><rect height="18" rx="1" width="2" x="132" y="1"></rect>
          <rect height="9" rx="1" width="2" x="136" y="6"></rect><rect height="15" rx="1" width="2" x="140" y="3"></rect>
          <rect height="7" rx="1" width="2" x="144" y="7"></rect><rect height="16" rx="1" width="2" x="148" y="2"></rect>
          <rect height="11" rx="1" width="2" x="152" y="5"></rect><rect height="18" rx="1" width="2" x="156" y="1"></rect>
          <rect height="12" rx="1" width="2" x="160" y="4"></rect><rect height="7" rx="1" width="2" x="164" y="7"></rect>
          <rect height="16" rx="1" width="2" x="168" y="2"></rect><rect height="11" rx="1" width="2" x="172" y="5"></rect>
          <rect height="17" rx="1" width="2" x="176" y="2"></rect><rect height="9" rx="1" width="2" x="180" y="6"></rect>
          <rect height="14" rx="1" width="2" x="184" y="3"></rect><rect height="7" rx="1" width="2" x="188" y="7"></rect>
          <rect height="16" rx="1" width="2" x="192" y="2"></rect><rect height="11" rx="1" width="2" x="196" y="5"></rect>
          <rect height="18" rx="1" width="2" x="200" y="1"></rect><rect height="12" rx="1" width="2" x="204" y="4"></rect>
          <rect height="7" rx="1" width="2" x="208" y="7"></rect><rect height="16" rx="1" width="2" x="212" y="2"></rect>
          <rect height="11" rx="1" width="2" x="216" y="5"></rect><rect height="18" rx="1" width="2" x="220" y="1"></rect>
          <rect height="9" rx="1" width="2" x="224" y="6"></rect><rect height="15" rx="1" width="2" x="228" y="3"></rect>
          <rect height="7" rx="1" width="2" x="232" y="7"></rect><rect height="16" rx="1" width="2" x="236" y="2"></rect>
          <rect height="11" rx="1" width="2" x="240" y="5"></rect><rect height="18" rx="1" width="2" x="244" y="1"></rect>
          <rect height="12" rx="1" width="2" x="248" y="4"></rect><rect height="7" rx="1" width="2" x="252" y="7"></rect>
          <rect height="16" rx="1" width="2" x="256" y="2"></rect><rect height="10" rx="1" width="2" x="260" y="5"></rect>
          <rect height="17" rx="1" width="2" x="264" y="2"></rect><rect height="9" rx="1" width="2" x="268" y="6"></rect>
          <rect height="14" rx="1" width="2" x="272" y="3"></rect><rect height="7" rx="1" width="2" x="276" y="7"></rect>
          <rect height="16" rx="1" width="2" x="280" y="2"></rect><rect height="11" rx="1" width="2" x="284" y="5"></rect>
          <rect height="18" rx="1" width="2" x="288" y="1"></rect><rect height="12" rx="1" width="2" x="292" y="4"></rect>
          <rect height="15" rx="1" width="2" x="296" y="3"></rect>
        </svg>

        <!-- Progress Highlight -->
        <div data-scrubber-progress class="absolute inset-y-0 left-0 bg-[#8D4B00]/20 rounded-l pointer-events-none" style="width: ${percent}%;"></div>
        <!-- Scrubber Marker -->
        <div data-scrubber-marker class="absolute top-0 bottom-0 w-2 bg-[#8D4B00] rounded shadow-xs pointer-events-none -ml-1" style="left: ${percent}%;"></div>
      </div>

      <!-- Transport Controls Row -->
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-1.5">
          <button 
            class="w-6 h-6 rounded-md bg-stone-100 hover:bg-stone-200 text-stone-700 flex items-center justify-center transition-colors" 
            title="Rewind 5s"
            onclick="window.dubDubStore.setPlaybackTime(Math.max(0, ${state.playback.currentTime} - 5))">
            <span class="material-symbols-outlined text-xs">replay_5</span>
          </button>

          <button 
            class="w-7 h-7 rounded-md bg-[#8D4B00] text-white hover:bg-[#743d00] flex items-center justify-center shadow-xs transition-transform active:scale-95" 
            title="${isPlaying ? 'Pause' : 'Play'}"
            onclick="window.dubDubStore.togglePlay()">
            <span class="material-symbols-outlined text-sm">${isPlaying ? 'pause' : 'play_arrow'}</span>
          </button>

          <button 
            class="w-6 h-6 rounded-md bg-stone-100 hover:bg-stone-200 text-stone-700 flex items-center justify-center transition-colors" 
            title="Forward 5s"
            onclick="window.dubDubStore.setPlaybackTime(Math.min(${state.project.durationSec}, ${state.playback.currentTime} + 5))">
            <span class="material-symbols-outlined text-xs">forward_5</span>
          </button>

          <div class="flex items-center gap-1 font-mono text-[10px] ml-1.5">
            <span data-playhead-timecode class="font-bold text-stone-900">${state.playback.formattedTime}</span>
            <span class="text-stone-300">/</span>
            <span class="text-stone-500">${state.project.duration}</span>
          </div>
        </div>

        <div class="flex items-center gap-2.5 text-[10px]">
          <span class="text-stone-500">Ducking: <strong class="text-stone-800 font-mono">${state.tuning.ducking}</strong></span>
          <span class="px-1.5 py-0.5 rounded bg-stone-100 text-stone-600 font-mono font-semibold">${state.playback.playbackSpeed.toFixed(1)}x</span>
        </div>
      </div>
    </div>
  `;
}
