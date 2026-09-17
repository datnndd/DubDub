/**
 * Reusable WorkflowStepper Component
 * Synchronized progress stepper displayed on all screens.
 */

export function renderWorkflowStepper(state) {
  const cur = state.currentStep;

  const steps = [
    { num: 1, label: "Prepare" },
    { num: 2, label: "Review Transcript" },
    { num: 3, label: "Voice & Dubbing" },
    { num: 4, label: "Edit Video" }
  ];

  const stageTelemetry = {
    1: `
      <span class="inline-flex items-center gap-1 text-stone-600 bg-stone-100 px-2.5 py-0.5 rounded-md border border-stone-200 text-[10px] font-medium">
        <span class="material-symbols-outlined text-xs text-[#8D4B00]">tune</span>
        <span>Stage 01: Pre-Flight Configuration</span>
      </span>
    `,
    2: `
      <span class="inline-flex items-center gap-1 text-amber-800 bg-amber-50 px-2.5 py-0.5 rounded-md border border-amber-200 text-[10px] font-semibold">
        <span class="material-symbols-outlined text-xs">document_scanner</span>
        <span>OCR Slide Engine: Active (1 Diff Pending)</span>
      </span>
    `,
    3: `
      <span class="inline-flex items-center gap-1 text-emerald-800 bg-emerald-50 px-2.5 py-0.5 rounded-md border border-emerald-200 text-[10px] font-semibold">
        <span class="material-symbols-outlined text-xs">sync</span>
        <span>Neural Voice Sync: 99.8%</span>
      </span>
    `,
    4: `
      <span class="inline-flex items-center gap-1 text-emerald-800 bg-emerald-50 px-2.5 py-0.5 rounded-md border border-emerald-200 text-[10px] font-semibold">
        <span class="material-symbols-outlined text-xs">layers</span>
        <span>Multi-Track Timeline: 5 Tracks Synced</span>
      </span>
    `
  };

  return `
    <div class="h-9 flex-shrink-0 bg-[#FAF8F5] border-b border-[#E7E4DC] px-4 flex items-center justify-between z-20">
      <!-- Media Identity Pill -->
      <div class="flex items-center gap-2">
        <div class="flex items-center gap-1.5 bg-white px-2.5 py-0.5 rounded-lg border border-stone-200 text-stone-700 shadow-2xs">
          <span class="material-symbols-outlined text-xs text-stone-400">movie</span>
          <span class="font-mono text-[11px] font-medium truncate max-w-[190px]">${state.project.filename}</span>
          <span class="px-1.5 py-0.2 bg-amber-50 text-amber-900 border border-amber-200/80 rounded font-mono font-bold text-[9px] tracking-wide uppercase leading-none">
            ${state.languages.source.code.split('-')[0].toUpperCase()} ➔ ${state.languages.target.code.split('-')[0].toUpperCase()}
          </span>
        </div>
      </div>

      <!-- Synchronized 4-Step Interactive Navigation -->
      <div class="flex items-center gap-1.5 bg-white px-2.5 py-0.5 rounded-full border border-[#E7E4DC] shadow-2xs">
        ${steps.map((s, idx) => {
          const isDone = s.num < cur;
          const isActive = s.num === cur;
          
          let content = '';
          if (isActive) {
            content = `
              <div class="flex items-center gap-1 text-[#8D4B00] text-[11px] font-bold bg-amber-50 px-2.5 py-0.5 rounded-full border border-amber-200 shadow-2xs cursor-pointer" onclick="window.dubDubStore.setStep(${s.num})">
                <span class="w-3.5 h-3.5 rounded-full bg-[#8D4B00] text-white flex items-center justify-center text-[9px] font-bold">${s.num}</span>
                <span>${s.label}</span>
              </div>
            `;
          } else if (isDone) {
            content = `
              <div class="flex items-center gap-1 text-stone-600 hover:text-stone-900 text-[11px] font-semibold cursor-pointer transition-colors px-1" onclick="window.dubDubStore.setStep(${s.num})">
                <span class="w-3.5 h-3.5 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-[9px] font-bold">✓</span>
                <span>${s.label}</span>
              </div>
            `;
          } else {
            content = `
              <div class="flex items-center gap-1 text-stone-400 hover:text-stone-600 text-[11px] font-medium cursor-pointer transition-colors px-1" onclick="window.dubDubStore.setStep(${s.num})">
                <span class="w-3.5 h-3.5 rounded-full bg-stone-200 text-stone-500 flex items-center justify-center text-[9px] font-semibold">${s.num}</span>
                <span>${s.label}</span>
              </div>
            `;
          }

          const separator = idx < steps.length - 1 ? `<span class="text-stone-300 text-[10px]">•</span>` : '';
          return `${content}${separator}`;
        }).join('')}
      </div>

      <!-- Right Telemetry Badge -->
      <div class="hidden xl:flex items-center gap-2">
        ${stageTelemetry[cur] || ''}
      </div>
    </div>
  `;
}
