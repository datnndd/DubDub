/**
 * FloatingPill Component
 * Always-on interactive HUD indicator for background dubbing tasks.
 * Displays live progress, elapsed timer, click-to-return navigation, and cancel action.
 */

function formatElapsed(secs) {
  if (!secs || secs < 0) return '0s';
  const mins = Math.floor(secs / 60);
  const s = secs % 60;
  if (mins > 0) return `${mins}:${String(s).padStart(2, '0')}`;
  return `${s}s`;
}

const STAGE_ICONS = {
  prepare: 'tune',
  recogn: 'graphic_eq',
  diariz: 'record_voice_over',
  trans: 'translate',
  dubbing: 'campaign',
  align: 'sync',
  assembling: 'video_settings',
  render: 'movie_creation',
  task_done: 'check_circle',
};

export function renderFloatingPill(state) {
  const backend = state.backend;
  if (!backend || !backend.jobId) return '';

  const status = backend.status;
  const isActive = ['running', 'queued', 'submitting'].includes(status);
  const isDone = status === 'succeeded';
  const isError = status === 'failed';
  const isCancelled = status === 'cancelled';

  // If idle and not active, don't show
  if (!isActive && !isDone && !isError && !isCancelled) return '';

  const stageIcon = STAGE_ICONS[backend.stage] || (isDone ? 'check_circle' : isError ? 'error' : 'hourglass_top');
  const projectName = state.project?.filename || 'Current Project';
  const progressVal = backend.progress != null ? Math.round(backend.progress) : null;
  const elapsedText = formatElapsed(backend.elapsedSeconds || 0);

  const borderClass = isError
    ? 'border-rose-300 bg-rose-50/95 text-rose-900 shadow-rose-200/50'
    : isDone
    ? 'border-emerald-300 bg-emerald-50/95 text-emerald-900 shadow-emerald-200/50'
    : 'border-amber-300 bg-white/95 text-stone-800 shadow-amber-900/10';

  return `
    <div
      class="fixed bottom-12 right-6 z-40 flex items-center gap-3 p-2.5 rounded-2xl border shadow-xl backdrop-blur-md transition-all duration-300 ${borderClass} max-w-sm cursor-pointer hover:scale-[1.02]"
      onclick="window.dubDubStore.navigateToActiveJob()"
      role="status"
      title="Click to view running stage"
    >
      <!-- Icon -->
      <div class="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 ${
        isActive ? 'bg-amber-100 text-[#8D4B00]' : isDone ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'
      }">
        <span class="material-symbols-outlined text-base ${isActive ? 'animate-spin' : ''}">
          ${isActive && !backend.stage ? 'progress_activity' : stageIcon}
        </span>
      </div>

      <!-- Text & Progress -->
      <div class="flex-1 min-w-0 pr-1">
        <div class="flex items-center justify-between gap-2">
          <span class="font-bold text-[11px] truncate text-stone-900">${projectName}</span>
          ${isActive ? `
            <span class="font-mono text-[10px] text-stone-500 font-semibold">${elapsedText}</span>
          ` : ''}
        </div>

        <div class="flex items-center justify-between gap-2 mt-0.5 text-[10px] text-stone-600">
          <span class="truncate">${backend.message || (isActive ? 'Processing...' : status)}</span>
          ${progressVal != null && isActive ? `
            <span class="font-mono font-bold text-[#8D4B00]">${progressVal}%</span>
          ` : ''}
        </div>

        ${isActive ? `
          <div class="w-full h-1.5 bg-stone-100 rounded-full overflow-hidden mt-1.5 border border-stone-200/60">
            <div
              class="h-full bg-gradient-to-r from-amber-500 to-[#8D4B00] transition-all duration-300 rounded-full ${progressVal == null ? 'animate-pulse w-2/3' : ''}"
              style="${progressVal != null ? `width: ${progressVal}%` : ''}"
            ></div>
          </div>
        ` : ''}
      </div>

      <!-- Action: Cancel or Dismiss -->
      <button
        onclick="event.stopPropagation(); ${isActive ? 'window.dubDubStore.cancelProcessing()' : 'window.dubDubStore.dismissPill()'}"
        class="w-6 h-6 rounded-full hover:bg-black/5 flex items-center justify-center text-stone-400 hover:text-stone-700 cursor-pointer flex-shrink-0"
        title="${isActive ? 'Cancel Job' : 'Dismiss'}"
      >
        <span class="material-symbols-outlined text-sm">close</span>
      </button>
    </div>
  `;
}
