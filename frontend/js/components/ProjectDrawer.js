/**
 * ProjectDrawer Component
 * Slide-out drawer displaying all persistent video dubbing projects
 * with live status indicators, switching, and deletion.
 */

export function renderProjectDrawer(state) {
  if (!state.drawerOpen) return '';

  const projects = state.projectsList || [];
  const activeId = state.activeProjectId;

  const stageLabels = {
    1: '1. Prepare & ASR',
    2: '2. Review Transcript',
    3: '3. Voice Dubbing',
    4: '4. Video Edit & Export'
  };

  const statusBadges = {
    pending: '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-stone-100 text-stone-600 border border-stone-200">Pending</span>',
    processing: '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200 flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse"></span>Processing</span>',
    completed: '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">Completed</span>',
    failed: '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">Failed</span>',
    paused: '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-yellow-50 text-yellow-700 border border-yellow-200">Paused</span>',
  };

  const formatTime = (ts) => {
    if (!ts) return 'Unknown';
    const d = new Date(ts * 1000);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return `
    <div class="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-xs transition-opacity" onclick="if (event.target === this) window.dubDubStore.closeDrawer()">
      <div class="w-full max-w-md h-full bg-white shadow-2xl flex flex-col border-l border-stone-200 animate-slide-in">
        <!-- Header -->
        <div class="h-[56px] px-4 border-b border-stone-200 flex items-center justify-between bg-stone-50/80">
          <div class="flex items-center gap-2">
            <span class="material-symbols-outlined text-[#8D4B00]">folder_open</span>
            <h2 class="font-bold text-stone-900 text-sm">Dubbing Projects</h2>
            <span class="px-2 py-0.5 text-[10px] font-semibold bg-amber-100 text-[#8D4B00] rounded-full">${projects.length}</span>
          </div>
          <div class="flex items-center gap-2">
            <button
              onclick="window.dubDubStore.startNewProject()"
              class="px-2.5 py-1 text-xs font-semibold rounded-md bg-[#8D4B00] text-white hover:bg-[#743D00] flex items-center gap-1 shadow-2xs cursor-pointer"
            >
              <span class="material-symbols-outlined text-xs">add</span>
              <span>New</span>
            </button>
            <button
              onclick="window.dubDubStore.closeDrawer()"
              class="w-7 h-7 rounded-md hover:bg-stone-200/60 flex items-center justify-center text-stone-500 cursor-pointer"
            >
              <span class="material-symbols-outlined text-base">close</span>
            </button>
          </div>
        </div>

        <!-- Project List -->
        <div class="flex-1 overflow-y-auto p-4 space-y-3">
          ${projects.length === 0 ? `
            <div class="h-64 flex flex-col items-center justify-center text-center p-6 text-stone-400">
              <span class="material-symbols-outlined text-4xl mb-2 text-stone-300">video_file</span>
              <p class="font-medium text-xs text-stone-600">No saved projects yet</p>
              <p class="text-[11px] text-stone-400 mt-1">Upload a video to create your first dubbing project.</p>
            </div>
          ` : projects.map(p => `
            <div class="p-3.5 rounded-xl border ${p.id === activeId ? 'border-[#8D4B00] bg-amber-50/30 ring-1 ring-[#8D4B00]/20' : 'border-stone-200 hover:border-stone-300 bg-white'} shadow-2xs transition-all">
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-1.5">
                    <span class="material-symbols-outlined text-stone-400 text-sm">movie</span>
                    <h3 class="font-bold text-xs text-stone-900 truncate" title="${p.name}">${p.name}</h3>
                  </div>
                  <div class="flex items-center gap-2 mt-1.5 text-[11px] text-stone-500">
                    <span class="font-medium text-stone-700">${stageLabels[p.stage] || 'Stage ' + p.stage}</span>
                    <span>•</span>
                    <span>${p.duration ? Math.round(p.duration) + 's' : '—'}</span>
                  </div>
                  <div class="text-[10px] text-stone-400 mt-1">
                    Updated ${formatTime(p.updated_at)}
                  </div>
                </div>
                <div class="flex flex-col items-end gap-2">
                  ${statusBadges[p.status] || statusBadges.pending}
                  <div class="flex items-center gap-1 mt-1">
                    <button
                      onclick="window.dubDubStore.loadProject('${p.id}')"
                      class="px-2 py-1 text-[11px] font-semibold rounded ${p.id === activeId ? 'bg-[#8D4B00] text-white' : 'bg-stone-100 hover:bg-stone-200 text-stone-700'} cursor-pointer"
                    >
                      ${p.id === activeId ? 'Active' : 'Switch'}
                    </button>
                    <button
                      onclick="if(confirm('Delete project \\'${p.name}\\'?')) window.dubDubStore.deleteProject('${p.id}')"
                      class="w-6 h-6 rounded flex items-center justify-center text-stone-400 hover:text-rose-600 hover:bg-rose-50 cursor-pointer"
                      title="Delete Project"
                    >
                      <span class="material-symbols-outlined text-xs">delete</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    </div>
  `;
}
