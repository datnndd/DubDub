/**
 * DubDub Studio Application Root Coordinator
 * Connects state, reusable components, and stage screens.
 */

import { store } from './state.js';
import { renderHeader } from './components/Header.js';
import { renderWorkflowStepper } from './components/WorkflowStepper.js';
import { renderStatusFooter } from './components/StatusFooter.js';
import { renderStage1Prepare, renderAsrProgressCard } from './screens/Stage1Prepare.js';
import { renderStage2ReviewTranscript } from './screens/Stage2ReviewTranscript.js';
import { renderStage3VoiceDubbing } from './screens/Stage3VoiceDubbing.js';
import { renderStage4EditVideo } from './screens/Stage4EditVideo.js';

function renderApp() {
  const root = document.getElementById('app');
  if (!root) return;

  const activeEl = document.activeElement;
  const activeInputId = activeEl?.getAttribute?.('data-segment-input');
  const selStart = (activeEl instanceof HTMLTextAreaElement || activeEl instanceof HTMLInputElement) ? activeEl.selectionStart : null;
  const selEnd = (activeEl instanceof HTMLTextAreaElement || activeEl instanceof HTMLInputElement) ? activeEl.selectionEnd : null;

  const state = store.getState();

  let stageHtml = '';
  switch (state.currentStep) {
    case 1:
      stageHtml = renderStage1Prepare(state);
      break;
    case 2:
      stageHtml = renderStage2ReviewTranscript(state);
      break;
    case 3:
      stageHtml = renderStage3VoiceDubbing(state);
      break;
    case 4:
      stageHtml = renderStage4EditVideo(state);
      break;
    default:
      stageHtml = renderStage1Prepare(state);
  }

  root.innerHTML = `
    <div class="h-screen w-screen overflow-hidden flex flex-col bg-[#F9F8F5] text-stone-800 font-sans antialiased select-none text-xs">
      ${renderHeader(state)}
      ${renderWorkflowStepper(state)}
      <main class="flex-1 min-h-0 w-full overflow-hidden flex flex-col">
        ${stageHtml}
      </main>
      ${renderStatusFooter(state)}
    </div>
  `;

  if (activeInputId != null) {
    const restored = document.querySelector(`[data-segment-input="${activeInputId}"]`);
    if (restored) {
      restored.focus();
      if (selStart != null && selEnd != null) {
        try { restored.setSelectionRange(selStart, selEnd); } catch (_) {}
      }
    }
  }
}

function renderStatusOnly() {
  const state = store.getState();
  const footer = document.querySelector('[data-status-footer]');
  if (footer) {
    footer.outerHTML = renderStatusFooter(state);
  } else {
    renderApp();
    return;
  }
  const progressCard = document.querySelector('[data-asr-progress]');
  if (progressCard) {
    const newHtml = renderAsrProgressCard(state.backend);
    if (newHtml) {
      progressCard.outerHTML = newHtml;
    }
  }
}

// Initial mount & subscribe to reactive state changes.
// ASR polling updates only the status footer so the active <video> element is
// not destroyed and recreated on every polling interval.
store.subscribe((_state, scope = 'full') => {
  if (scope === 'status') {
    renderStatusOnly();
    return;
  }
  renderApp();
});

document.addEventListener('DOMContentLoaded', () => {
  renderApp();
  const mediaInput = document.getElementById('media-input');
  mediaInput?.addEventListener('change', () => store.selectMedia(mediaInput.files?.[0]));
  store.initialize();
});
