import React from 'react';
import { useDubDubStore } from '../store';
import { FolderOpen, Plus, X, Film, Trash2 } from 'lucide-react';

export const ProjectDrawer: React.FC = () => {
  const drawerOpen = useDubDubStore((s) => s.drawerOpen);
  const setDrawerOpen = useDubDubStore((s) => s.setDrawerOpen);
  const projectsList = useDubDubStore((s) => s.projectsList);
  const activeProjectId = useDubDubStore((s) => s.activeProjectId);
  const selectProject = useDubDubStore((s) => s.selectProject);
  const createNewProject = useDubDubStore((s) => s.createNewProject);
  const deleteProjectById = useDubDubStore((s) => s.deleteProjectById);

  if (!drawerOpen) return null;

  const stageLabels: Record<number, string> = {
    1: '1. Prepare & ASR',
    2: '2. Review Transcript',
    3: '3. Voice Dubbing',
    4: '4. Video Edit & Export',
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'processing':
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
            Processing
          </span>
        );
      case 'completed':
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            Completed
          </span>
        );
      case 'failed':
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            Failed
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-stone-100 text-stone-600 border border-stone-200">
            Pending
          </span>
        );
    }
  };

  return (
    <div
      data-project-drawer="true"
      className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-xs transition-opacity"
      onClick={(e) => {
        if (e.target === e.currentTarget) setDrawerOpen(false);
      }}
    >
      <div className="w-full max-w-md h-full bg-white shadow-2xl flex flex-col border-l border-stone-200 animate-slide-in">
        {/* Header */}
        <div className="h-[56px] px-4 border-b border-stone-200 flex items-center justify-between bg-stone-50/80">
          <div className="flex items-center gap-2">
            <FolderOpen className="w-4 h-4 text-[#8D4B00]" />
            <h2 className="font-bold text-stone-900 text-sm">Dubbing Projects</h2>
            <span className="px-2 py-0.5 text-[10px] font-semibold bg-amber-100 text-[#8D4B00] rounded-full">
              {projectsList.length}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => createNewProject()}
              className="px-2.5 py-1 text-xs font-semibold rounded-md bg-[#8D4B00] text-white hover:bg-[#743D00] flex items-center gap-1 shadow-2xs cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>New</span>
            </button>
            <button
              onClick={() => setDrawerOpen(false)}
              className="w-7 h-7 rounded-md hover:bg-stone-200/60 flex items-center justify-center text-stone-500 cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Project List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {projectsList.length === 0 ? (
            <div className="h-64 flex flex-col items-center justify-center text-center p-6 text-stone-400">
              <Film className="w-8 h-8 mb-2 text-stone-300" />
              <p className="font-medium text-xs text-stone-600">No saved projects yet</p>
              <p className="text-[11px] text-stone-400 mt-1">Upload a video to create your first dubbing project.</p>
            </div>
          ) : (
            projectsList.map((p) => {
              const isActive = p.id === activeProjectId;
              return (
                <div
                  key={p.id}
                  className={`p-3.5 rounded-xl border ${
                    isActive
                      ? 'border-[#8D4B00] bg-amber-50/30 ring-1 ring-[#8D4B00]/20'
                      : 'border-stone-200 hover:border-stone-300 bg-white'
                  } shadow-2xs transition-all`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <Film className="w-3.5 h-3.5 text-stone-400 shrink-0" />
                        <h3 className="font-bold text-xs text-stone-900 truncate" title={p.name}>
                          {p.name}
                        </h3>
                      </div>
                      <div className="flex items-center gap-2 mt-1.5 text-[11px] text-stone-500">
                        <span className="font-medium text-stone-700">
                          {stageLabels[p.stage] || `Stage ${p.stage}`}
                        </span>
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      {getStatusBadge(p.status)}
                      <div className="flex items-center gap-1 mt-1">
                        <button
                          onClick={() => selectProject(p.id)}
                          className={`px-2 py-1 text-[11px] font-semibold rounded cursor-pointer ${
                            isActive
                              ? 'bg-[#8D4B00] text-white'
                              : 'bg-stone-100 hover:bg-stone-200 text-stone-700'
                          }`}
                        >
                          {isActive ? 'Active' : 'Switch'}
                        </button>
                        <button
                          onClick={() => {
                            if (window.confirm(`Delete project "${p.name}"?`)) {
                              deleteProjectById(p.id);
                            }
                          }}
                          className="w-6 h-6 rounded flex items-center justify-center text-stone-400 hover:text-rose-600 hover:bg-rose-50 cursor-pointer"
                          title="Delete Project"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
