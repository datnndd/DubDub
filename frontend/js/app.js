/**
 * DubDub Studio Application Root Coordinator
 * Connects state, reusable components, and stage screens.
 */

import { store } from './state.js';
import { renderHeader } from './components/Header.js';
import { renderWorkflowStepper } from './components/WorkflowStepper.js';
import { renderStatusFooter } from './components/StatusFooter.js';
import { renderStage1Prepare } from './screens/Stage1Prepare.js';
import { renderStage2ReviewTranscript } from './screens/Stage2ReviewTranscript.js';
import { renderStage3VoiceDubbing } from './screens/Stage3VoiceDubbing.js';
import { renderStage4EditVideo } from './screens/Stage4EditVideo.js';

function renderApp() {
  const root = document.getElementById('app');
  if (!root) return;

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
}

function renderStatusOnly() {
  const footer = document.querySelector('[data-status-footer]');
  if (!footer) {
    renderApp();
    return;
  }
  footer.outerHTML = renderStatusFooter(store.getState());
}

// Initial mount & subscribe to reactive state changes.
// Job polling updates only the status footer so the active <video> node is not
// destroyed and recreated every 750 ms while ASR is running.
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
