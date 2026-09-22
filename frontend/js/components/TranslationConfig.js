/**
 * Reusable TranslationConfig Component
 * Shared LLM Translation configuration deck for Prepare Stage and Review Transcript Stage.
 */

export function renderTranslationConfig(state, options = {}) {
  const {
    containerClass = "col-span-12 md:col-span-6 lg:col-span-3 h-full",
    title = "Translation LLM",
    headerHeight = "h-7",
    badge = "Reasoning"
  } = options;

  const backend = state.backend;
  const opt = backend.options;
  const escapeHtml = value => String(value || '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);

  const selectedTranslation = (opt.translationProviders || []).find(
    item => item.translateType === Number(backend.config.translateType)
  ) || (opt.translationProviders && opt.translationProviders[0]) || {
    id: '',
    label: 'Unavailable',
    requiresSettings: false,
    configured: false
  };

  const translationTags = (opt.translationProviders || []).map(provider =>
    `<option value="${provider.translateType}" ${provider.translateType === Number(backend.config.translateType) ? 'selected' : ''}>${escapeHtml(provider.label)}</option>`
  ).join('');

  const translationModes = opt.translationModes || [];
  const translationSettingsProvider = backend.translationSettingsProviderId
    ? (opt.translationProviders || []).find(item => item.id && item.id === backend.translationSettingsProviderId)
    : null;

  return `
    <div class="${containerClass} bg-white rounded-xl border border-[#E7E4DC] shadow-xs flex flex-col min-h-0 overflow-hidden">
      <!-- Header -->
      <div class="${headerHeight} px-3 border-b border-[#E7E4DC] bg-[#FAF9F6] flex items-center justify-between flex-shrink-0">
        <div class="flex items-center gap-1.5">
          <span class="material-symbols-outlined text-[#8D4B00] text-sm">psychology</span>
          <h3 class="text-xs font-bold text-stone-900">${escapeHtml(title)}</h3>
        </div>
        <span class="px-1.5 py-0.2 bg-stone-100 text-stone-600 rounded text-[9px] font-mono font-bold">${escapeHtml(badge)}</span>
      </div>

      <!-- Configuration Body -->
      <div class="flex-1 min-h-0 p-2.5 flex flex-col justify-start overflow-y-auto space-y-2">
        <div>
          <label class="text-[9px] font-bold text-stone-400 uppercase tracking-wider block mb-1">Translation Provider</label>
          <select class="w-full bg-white text-xs font-bold text-stone-800 py-1 px-2 rounded-lg border border-amber-300 focus:outline-none focus:ring-1 focus:ring-primary" onchange="window.dubDubStore.updateBackendConfig('translateType', Number(this.value))">
            ${translationTags}
          </select>
          <div class="flex items-center gap-1.5 mt-1.5">
            ${selectedTranslation.requiresSettings ? `
              <button type="button" onclick="window.dubDubStore.openTranslationSettings('${selectedTranslation.id}')" class="flex-1 h-6.5 px-2 rounded-md border ${selectedTranslation.configured ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-amber-300 bg-amber-50 text-[#8D4B00]'} text-[9px] font-bold flex items-center justify-center gap-1 hover:brightness-95 transition-colors">
                <span class="material-symbols-outlined text-xs">tune</span>
                API Settings
              </button>
            ` : ''}
            <button type="button" ${backend.translationTesting ? 'disabled' : ''} onclick="window.dubDubStore.testTranslationConnection('${selectedTranslation.id}')" class="${selectedTranslation.requiresSettings ? 'flex-1' : 'w-full'} h-6.5 px-2 rounded-md border border-stone-200 bg-stone-50 hover:bg-stone-100 disabled:opacity-50 text-stone-700 text-[9px] font-bold flex items-center justify-center gap-1 transition-colors">
              <span class="material-symbols-outlined text-xs">${backend.translationTesting && backend.translationTestProviderId === selectedTranslation.id ? 'progress_activity' : 'network_check'}</span>
              ${backend.translationTesting && backend.translationTestProviderId === selectedTranslation.id ? 'Testing…' : 'Test connection'}
            </button>
          </div>
          ${selectedTranslation.requiresSettings ? `
            <p class="mt-1 text-[9px] ${selectedTranslation.configured ? 'text-emerald-700' : 'text-amber-700'}">
              ${selectedTranslation.configured ? `${escapeHtml(selectedTranslation.model)} configured` : 'API settings required before processing'}
            </p>
          ` : ''}
          ${backend.translationTestProviderId === selectedTranslation.id && backend.translationTestMessage ? `
            <p class="mt-1 text-[9px] ${backend.translationTestOk === false ? 'text-red-700' : backend.translationTestOk ? 'text-emerald-700' : 'text-stone-500'} truncate" title="${escapeHtml(backend.translationTestMessage)}">${escapeHtml(backend.translationTestMessage)}</p>
          ` : ''}
        </div>

        <!-- Translation Mode -->
        <div>
          <label class="text-[9px] font-bold text-stone-400 uppercase tracking-wider block mb-1">Translation Mode</label>
          ${selectedTranslation.id === 'google' ? `
            <div class="p-1.5 rounded-md bg-stone-50 border border-stone-200 text-[9px] text-stone-500">
              Google Translate uses the existing line-by-line provider flow.
            </div>
          ` : `
            <div class="grid grid-cols-2 gap-1">
              ${translationModes.map(mode => `
                <label title="${escapeHtml(mode.description)}" class="p-1.5 rounded-md border cursor-pointer transition-colors ${backend.config.translationMode === mode.id ? 'border-[#8D4B00] bg-amber-50 text-[#8D4B00]' : 'border-stone-200 bg-stone-50 text-stone-600 hover:bg-stone-100'}">
                  <input class="sr-only" type="radio" name="translation_mode" value="${mode.id}" ${backend.config.translationMode === mode.id ? 'checked' : ''} onchange="window.dubDubStore.updateBackendConfig('translationMode', this.value)" />
                  <span class="block text-[10px] font-bold">${escapeHtml(mode.label)}</span>
                  <span class="block mt-0.5 text-[8px] leading-tight text-stone-500">${escapeHtml(mode.description)}</span>
                </label>
              `).join('')}
            </div>
          `}
        </div>
      </div>

      <!-- Translation Settings Modal (rendered when this provider's settings are opened) -->
      ${translationSettingsProvider ? `
        <div class="fixed inset-0 z-50 bg-stone-950/45 backdrop-blur-[1px] flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="translation-settings-title">
          <div class="w-full max-w-lg rounded-xl border border-[#E7E4DC] bg-white shadow-2xl overflow-hidden">
            <div class="h-10 px-4 bg-[#FAF9F6] border-b border-[#E7E4DC] flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="material-symbols-outlined text-[#8D4B00] text-base">translate</span>
                <h3 id="translation-settings-title" class="text-xs font-bold text-stone-900">${escapeHtml(translationSettingsProvider.label)} Settings</h3>
              </div>
              <button type="button" ${backend.translationSettingsSaving || backend.translationTesting ? 'disabled' : ''} onclick="window.dubDubStore.closeTranslationSettings()" class="text-stone-400 hover:text-stone-700 disabled:opacity-40">
                <span class="material-symbols-outlined text-lg">close</span>
              </button>
            </div>
            <div class="p-4 space-y-3">
              <p class="text-[11px] text-stone-600">Configure the endpoint and model used by the local translation backend. Stored API keys are never returned to this screen.</p>
              <div>
                <label for="translation-base-url" class="text-[9px] font-bold text-stone-500 uppercase tracking-wider block mb-1">Base URL</label>
                <input id="translation-base-url" type="url" value="${escapeHtml(translationSettingsProvider.baseUrl)}" ${backend.translationSettingsSaving || backend.translationTesting ? 'disabled' : ''} placeholder="Use the provider default endpoint" class="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-xs text-stone-800 focus:outline-none focus:ring-1 focus:ring-[#8D4B00]" />
              </div>
              <div>
                <label for="translation-api-key" class="text-[9px] font-bold text-stone-500 uppercase tracking-wider block mb-1">API Key</label>
                <input id="translation-api-key" type="password" autocomplete="new-password" ${backend.translationSettingsSaving || backend.translationTesting ? 'disabled' : ''} placeholder="${translationSettingsProvider.configured ? 'Leave blank to keep the stored key' : 'Paste an API key'}" class="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-xs text-stone-800 focus:outline-none focus:ring-1 focus:ring-[#8D4B00]" />
              </div>
              <div>
                <label for="translation-model" class="text-[9px] font-bold text-stone-500 uppercase tracking-wider block mb-1">Model</label>
                <input id="translation-model" list="translation-model-options" value="${escapeHtml(translationSettingsProvider.model)}" ${backend.translationSettingsSaving || backend.translationTesting ? 'disabled' : ''} placeholder="Enter a model name" class="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-xs text-stone-800 focus:outline-none focus:ring-1 focus:ring-[#8D4B00]" />
                <datalist id="translation-model-options">
                  ${(translationSettingsProvider.models || []).map(model => `<option value="${escapeHtml(model)}"></option>`).join('')}
                </datalist>
              </div>
              ${backend.translationSettingsError ? `<p class="rounded-lg border border-red-200 bg-red-50 px-2 py-1.5 text-[10px] text-red-700">${escapeHtml(backend.translationSettingsError)}</p>` : ''}
              ${backend.translationTestProviderId === translationSettingsProvider.id && backend.translationTestMessage && backend.translationTestOk ? `<p class="rounded-lg border border-emerald-200 bg-emerald-50 px-2 py-1.5 text-[10px] text-emerald-700">${escapeHtml(backend.translationTestMessage)}</p>` : ''}
              <div class="flex items-center justify-end gap-2 pt-1">
                <button type="button" ${backend.translationSettingsSaving || backend.translationTesting ? 'disabled' : ''} onclick="window.dubDubStore.closeTranslationSettings()" class="px-3 py-1.5 rounded-lg border border-stone-200 bg-white text-[10px] font-bold text-stone-600 disabled:opacity-40">Cancel</button>
                <button type="button" ${backend.translationSettingsSaving || backend.translationTesting ? 'disabled' : ''} onclick="window.dubDubStore.testTranslationConnection('${translationSettingsProvider.id}', true)" class="px-3 py-1.5 rounded-lg border border-[#8D4B00] bg-amber-50 text-[#8D4B00] text-[10px] font-bold disabled:opacity-50 flex items-center gap-1">
                  <span class="material-symbols-outlined text-xs">${backend.translationTesting ? 'progress_activity' : 'network_check'}</span>
                  ${backend.translationTesting ? 'Testing…' : 'Save & Test'}
                </button>
                <button type="button" ${backend.translationSettingsSaving || backend.translationTesting ? 'disabled' : ''} onclick="window.dubDubStore.saveTranslationSettings()" class="px-3 py-1.5 rounded-lg bg-[#8D4B00] text-white text-[10px] font-bold disabled:opacity-50 flex items-center gap-1">
                  <span class="material-symbols-outlined text-xs">${backend.translationSettingsSaving ? 'progress_activity' : 'save'}</span>
                  ${backend.translationSettingsSaving ? 'Saving…' : 'Save settings'}
                </button>
              </div>
            </div>
          </div>
        </div>
      ` : ''}
    </div>
  `;
}
