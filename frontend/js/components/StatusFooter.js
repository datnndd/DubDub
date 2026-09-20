/**
 * Reusable StatusFooter Component
 * Bottom persistent action dock with verification status and step navigation.
 */

export function renderStatusFooter(state) {
  const step = state.currentStep;
  const backend = state.backend;
  const busy = ['analyzing', 'submitting', 'queued', 'running'].includes(backend.status);
  const cancellable = ['queued', 'running'].includes(backend.status);

  const messages = {
    1: {
      icon: "check",
      title: "All media & engine parameters verified.",
      subtitle: "Ready for neural synthesis & transcription."
    },
    2: {
      icon: "document_scanner",
      title: "Transcript & OCR cues analyzed.",
      subtitle: "1 slide OCR diff highlighted for operator review."
    },
    3: {
      icon: "graphic_eq",
      title: "Neural voices assigned and synchronized.",
      subtitle: "48 dialogue cues ready for master timeline."
    },
    4: {
      icon: "movie_creation",
      title: "Master timeline sequenced.",
      subtitle: "AI Lip-Mesh & dynamic subtitles ready for 4K export."
    }
  };

  const primaryActions = {
    1: { text: "Start Processing & Translate", nextStep: 2, icon: "arrow_forward" },
    2: { text: "Proceed to Voice & Dubbing", nextStep: 3, icon: "arrow_forward" },
    3: { text: "Proceed to Edit Video", nextStep: 4, icon: "arrow_forward" },
    4: { text: "Export 4K Master Video", nextStep: null, icon: "file_download" }
  };

  const curMsg = messages[step] || messages[1];
  const curAction = primaryActions[step] || primaryActions[1];
  const escapeHtml = value => String(value || '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
  const liveTitle = escapeHtml(backend.error || (step === 1 ? backend.message : backend.status !== 'idle' ? backend.message : curMsg.title));
  const liveSubtitle = busy && backend.stage
    ? `Current stage: ${backend.stage}${backend.progress == null ? '' : ` • ${backend.progress.toFixed(1)}%`}`
    : step === 1 && !state.project.verified
      ? 'Upload a video, then choose languages and backend engines.'
      : curMsg.subtitle;
  const statusIcon = backend.status === 'failed' ? 'error' : busy ? 'progress_activity' : backend.status === 'succeeded' ? 'check_circle' : curMsg.icon;
  const statusColor = backend.status === 'failed' ? 'bg-red-100 text-red-700' : busy ? 'bg-amber-100 text-[#8D4B00]' : 'bg-emerald-100 text-emerald-700';
  const terminalOutputs = backend.outputs.map(output => `
    <a class="px-3 py-1.5 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-xs" href="${output.url}">${escapeHtml(output.name)}</a>
  `).join('');
  let actionText = curAction.text;
  let action = curAction.nextStep ? `window.dubDubStore.setStep(${curAction.nextStep})` : `alert('This editing/export control is not connected yet.')`;
  let actionIcon = curAction.icon;
  let actionDisabled = false;
  if (step === 1) {
    if (cancellable) {
      actionText = 'Cancel Processing';
      action = 'window.dubDubStore.cancelProcessing()';
      actionIcon = 'stop_circle';
    } else if (busy) {
      actionText = backend.status === 'analyzing' ? 'Inspecting Media…' : 'Starting Workflow…';
      action = '';
      actionIcon = 'progress_activity';
      actionDisabled = true;
    } else if (backend.status === 'succeeded') {
      actionText = 'Processing Complete';
      action = '';
      actionIcon = 'check_circle';
      actionDisabled = true;
    } else {
      actionText = state.project.verified ? 'Start Processing & Translate' : 'Choose Source Video';
      action = state.project.verified ? 'window.dubDubStore.startProcessing()' : 'window.dubDubStore.chooseMedia()';
      actionIcon = state.project.verified ? 'play_arrow' : 'upload_file';
      actionDisabled = state.project.verified && Boolean(window.dubDubStore.getPrepareValidationError());
    }
  }

  return `
    <footer data-status-footer class="h-[46px] flex-shrink-0 bg-white border-t border-[#E7E4DC] px-4 flex items-center justify-between gap-3 z-30 shadow-2xs">
      <!-- Left: Verification Status Checkmark -->
      <div class="flex items-center gap-2 min-w-0">
        <div class="w-5 h-5 rounded-full ${statusColor} flex items-center justify-center flex-shrink-0">
          <span class="material-symbols-outlined text-xs font-bold">${statusIcon}</span>
        </div>
        <span class="text-xs font-bold text-stone-800 truncate">
          ${liveTitle}
          <span class="font-normal text-stone-500 hidden sm:inline ml-1">${liveSubtitle}</span>
        </span>
      </div>

      <!-- Right: Bottom Action Buttons -->
      <div class="flex items-center gap-2 flex-shrink-0">
        ${backend.status === 'succeeded' ? terminalOutputs : ''}
        ${step > 1 ? `
          <button 
            class="px-3 py-1.5 rounded-lg bg-stone-100 hover:bg-stone-200 text-stone-700 font-semibold text-xs border border-stone-200 transition-colors flex items-center gap-1"
            onclick="window.dubDubStore.prevStep()">
            <span class="material-symbols-outlined text-xs">arrow_back</span>
            <span>Back</span>
          </button>
        ` : `
          <button disabled title="Profile saving is not connected yet" class="px-3 py-1.5 rounded-lg bg-stone-100 text-stone-400 font-semibold text-xs border border-stone-200 flex items-center gap-1.5 cursor-not-allowed">
            <span class="material-symbols-outlined text-xs text-stone-500">bookmark</span>
            <span>Save Profile</span>
          </button>
        `}

        <button 
          ${actionDisabled ? 'disabled' : ''}
          class="px-4 py-1.5 rounded-lg bg-[#8D4B00] hover:bg-[#743d00] disabled:bg-stone-300 disabled:text-stone-500 disabled:cursor-not-allowed text-white font-bold text-xs shadow-xs transition-colors flex items-center gap-1.5 active:scale-98"
          onclick="${action}">
          <span>${actionText}</span>
          <span class="material-symbols-outlined text-sm">${actionIcon}</span>
        </button>
      </div>
    </footer>
  `;
}
