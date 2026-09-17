/**
 * Reusable Header Component
 * Top Command Bar shared across all 4 stages.
 */

export function renderHeader(state) {
  return `
    <header class="h-[50px] flex-shrink-0 bg-white border-b border-[#E7E4DC] px-4 flex items-center justify-between gap-4 z-30 shadow-2xs">
      <!-- Left: DubDub Branding & Workspace Navigation -->
      <div class="flex items-center gap-3 min-w-0">
        <div class="flex items-center gap-2 cursor-pointer" onclick="window.dubDubStore.setStep(1)">
          <div class="w-8 h-8 rounded-lg bg-amber-500/15 text-[#8D4B00] flex items-center justify-center border border-amber-500/25 shadow-2xs">
            <span class="material-symbols-outlined text-lg">graphic_eq</span>
          </div>
          <div class="flex flex-col leading-none">
            <span class="font-bold text-xs tracking-tight text-stone-900">DubDub</span>
            <span class="text-[10px] text-stone-400 font-medium mt-0.5">Voice &amp; Subtitles Studio</span>
          </div>
        </div>

        <div class="h-4 w-px bg-stone-200"></div>

        <!-- Navigation Tabs -->
        <nav class="flex items-center gap-1 p-0.5 bg-stone-100/80 rounded-lg border border-stone-200/80 text-[11px]">
          <button class="px-2.5 py-1 rounded-md font-bold bg-white text-[#8D4B00] shadow-2xs border border-amber-200/80 flex items-center gap-1 leading-none">
            <span class="material-symbols-outlined text-xs">videocam</span>
            <span>Video Dub</span>
          </button>
          <button class="px-2.5 py-1 rounded-md font-medium text-stone-600 hover:text-stone-900 transition-colors flex items-center gap-1 leading-none">
            <span class="material-symbols-outlined text-xs text-stone-400">record_voice_over</span>
            <span>Manage Voice</span>
          </button>
          <button class="px-2.5 py-1 rounded-md font-medium text-stone-600 hover:text-stone-900 transition-colors flex items-center gap-1 leading-none">
            <span class="material-symbols-outlined text-xs text-stone-400">auto_stories</span>
            <span>Audio Book</span>
          </button>
        </nav>
      </div>

      <!-- Center-Right: AI Enhancers Quick Pill (for stage 4) or Stage Title -->
      <div class="hidden lg:flex items-center gap-1 text-[11px] text-stone-600">
        <span class="w-2 h-2 rounded-full bg-[#8D4B00]"></span>
        <span class="font-medium text-stone-700">Project: <strong class="text-stone-900">${state.project.filename}</strong></span>
      </div>

      <!-- Right: Auto-save & Warm GPU status -->
      <div class="flex items-center gap-3 flex-shrink-0">
        <div class="hidden sm:flex items-center gap-1 text-[11px] text-stone-500 font-medium">
          <span class="material-symbols-outlined text-xs text-stone-400">auto_fix_high</span>
          <span>Auto-saved ${state.project.lastSaved}</span>
        </div>
        <div class="flex items-center gap-2 px-2.5 py-1 bg-stone-50 rounded-lg border border-stone-200 shadow-2xs">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 warm-pulse"></span>
          <span class="font-mono text-[10px] font-semibold text-stone-700">${state.gpuStatus.warmDuration} Warm GPU</span>
        </div>
      </div>
    </header>
  `;
}
