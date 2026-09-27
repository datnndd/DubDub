import React, { useState, useMemo } from 'react';
import { useDubDubStore } from '../store';
import {
  FolderOpen,
  Plus,
  X,
  Film,
  Trash2,
  CheckSquare,
  Square,
  MinusSquare,
  Search,
  AlertTriangle,
  Loader2,
  CheckCircle2,
} from 'lucide-react';

export const ProjectDrawer: React.FC = () => {
  const drawerOpen = useDubDubStore((s) => s.drawerOpen);
  const setDrawerOpen = useDubDubStore((s) => s.setDrawerOpen);
  const projectsList = useDubDubStore((s) => s.projectsList);
  const activeProjectId = useDubDubStore((s) => s.activeProjectId);
  const selectProject = useDubDubStore((s) => s.selectProject);
  const createNewProject = useDubDubStore((s) => s.createNewProject);
  const deleteProjectById = useDubDubStore((s) => s.deleteProjectById);
  const deleteProjectsByIds = useDubDubStore((s) => s.deleteProjectsByIds);

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const stageLabels: Record<number, string> = {
    1: '1. Prepare & ASR',
    2: '2. Review Transcript',
    3: '3. Voice Dubbing',
    4: '4. Video Edit & Export',
  };

  const filteredProjects = useMemo(() => {
    if (!searchQuery.trim()) return projectsList;
    const q = searchQuery.toLowerCase();
    return projectsList.filter((p) => {
      const name = (p.name || '').toLowerCase();
      const stage = (stageLabels[p.stage] || `Stage ${p.stage}`).toLowerCase();
      const status = (p.status || '').toLowerCase();
      return name.includes(q) || stage.includes(q) || status.includes(q);
    });
  }, [projectsList, searchQuery]);

  if (!drawerOpen) return null;

  const allFilteredSelected =
    filteredProjects.length > 0 && filteredProjects.every((p) => selectedIds.has(p.id));
  const someFilteredSelected =
    filteredProjects.some((p) => selectedIds.has(p.id)) && !allFilteredSelected;

  const toggleSelect = (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (allFilteredSelected) {
      setSelectedIds(new Set());
    } else {
      const allIds = new Set(filteredProjects.map((p) => p.id));
      setSelectedIds(allIds);
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    setIsDeleting(true);
    try {
      const idsToDelete = Array.from(selectedIds);
      await deleteProjectsByIds(idsToDelete);
      setSelectedIds(new Set());
      setConfirmDeleteOpen(false);
    } catch (err) {
      console.error('Failed to delete selected projects:', err);
    } finally {
      setIsDeleting(false);
    }
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
      <div className="w-full max-w-lg h-full bg-white shadow-2xl flex flex-col border-l border-stone-200 animate-slide-in">
        {/* Header */}
        <div className="h-[56px] px-4 border-b border-stone-200 flex items-center justify-between bg-stone-50/80 shrink-0">
          <div className="flex items-center gap-2">
            <FolderOpen className="w-4 h-4 text-[#8D4B00]" />
            <h2 className="font-bold text-stone-900 text-sm">Project Manager</h2>
            <span className="px-2 py-0.5 text-[10px] font-semibold bg-amber-100 text-[#8D4B00] rounded-full">
              {projectsList.length}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={async () => {
                await createNewProject();
                setDrawerOpen(false);
              }}
              className="px-2.5 py-1 text-xs font-semibold rounded-md bg-[#8D4B00] text-white hover:bg-[#743D00] flex items-center gap-1 shadow-2xs cursor-pointer transition-colors"
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

        {/* Search & Bulk Selection Control Bar */}
        <div className="px-4 py-2.5 border-b border-stone-200 bg-white space-y-2 shrink-0">
          {/* Search Box */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-stone-400" />
            <input
              type="text"
              placeholder="Search projects by name, stage, or status…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1 text-xs bg-stone-50 rounded-lg border border-stone-200 focus:bg-white focus:outline-none focus:border-[#8D4B00] transition-colors"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-700"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>

          {/* Bulk Action Strip */}
          <div className="flex items-center justify-between gap-2 pt-1 text-xs">
            <div className="flex items-center gap-2">
              <button
                type="button"
                data-testid="select-all-projects-btn"
                onClick={toggleSelectAll}
                className="flex items-center gap-1.5 font-semibold text-stone-700 hover:text-stone-900 cursor-pointer px-1 py-0.5 rounded hover:bg-stone-100 transition-colors"
                title={allFilteredSelected ? 'Deselect all projects' : 'Select all projects'}
              >
                {allFilteredSelected ? (
                  <CheckSquare className="w-4 h-4 text-[#8D4B00]" />
                ) : someFilteredSelected ? (
                  <MinusSquare className="w-4 h-4 text-[#8D4B00]" />
                ) : (
                  <Square className="w-4 h-4 text-stone-400" />
                )}
                <span>
                  {allFilteredSelected
                    ? 'Deselect All'
                    : `Select All (${filteredProjects.length})`}
                </span>
              </button>

              {selectedIds.size > 0 && (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-[#8D4B00]">
                  {selectedIds.size} selected
                </span>
              )}
            </div>

            {selectedIds.size > 0 && (
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  data-testid="clear-selection-btn"
                  onClick={() => setSelectedIds(new Set())}
                  className="px-2 py-1 text-[11px] font-medium text-stone-500 hover:text-stone-800 hover:bg-stone-100 rounded cursor-pointer transition-colors"
                >
                  Clear
                </button>
                <button
                  type="button"
                  data-testid="bulk-delete-btn"
                  onClick={() => setConfirmDeleteOpen(true)}
                  className="px-2.5 py-1 text-[11px] font-bold bg-rose-600 hover:bg-rose-700 text-white rounded-md flex items-center gap-1 cursor-pointer transition-colors shadow-2xs"
                  title="Delete selected projects"
                >
                  <Trash2 className="w-3 h-3" />
                  <span>Delete Selected ({selectedIds.size})</span>
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Confirmation Banner / Modal for Deletion */}
        {confirmDeleteOpen && (
          <div className="p-3 bg-rose-50 border-b border-rose-200 flex flex-col gap-2 shrink-0 animate-fade-in">
            <div className="flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <div className="flex-1 text-xs text-rose-900 font-medium">
                Are you sure you want to delete{' '}
                <strong>
                  {selectedIds.size} {selectedIds.size === 1 ? 'project' : 'projects'}
                </strong>
                ? All associated transcription, dubbing audio, and video assets will be permanently removed.
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 mt-1">
              <button
                type="button"
                onClick={() => setConfirmDeleteOpen(false)}
                disabled={isDeleting}
                className="px-2.5 py-1 rounded bg-white border border-stone-200 text-xs font-semibold text-stone-700 hover:bg-stone-50 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                data-testid="confirm-bulk-delete-btn"
                onClick={handleBulkDelete}
                disabled={isDeleting}
                className="px-3 py-1 rounded bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold flex items-center gap-1 shadow-2xs cursor-pointer disabled:opacity-50"
              >
                {isDeleting ? (
                  <>
                    <Loader2 className="w-3 h-3 animate-spin" />
                    <span>Deleting…</span>
                  </>
                ) : (
                  <>
                    <Trash2 className="w-3 h-3" />
                    <span>Confirm Delete ({selectedIds.size})</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* Project List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
          {filteredProjects.length === 0 ? (
            <div className="h-64 flex flex-col items-center justify-center text-center p-6 text-stone-400">
              <Film className="w-8 h-8 mb-2 text-stone-300" />
              <p className="font-medium text-xs text-stone-600">
                {searchQuery ? 'No matching projects found' : 'No saved projects yet'}
              </p>
              <p className="text-[11px] text-stone-400 mt-1">
                {searchQuery
                  ? 'Try searching with a different keyword.'
                  : 'Upload a video to create your first dubbing project.'}
              </p>
            </div>
          ) : (
            filteredProjects.map((p) => {
              const isActive = p.id === activeProjectId;
              const isSelected = selectedIds.has(p.id);

              return (
                <div
                  key={p.id}
                  data-project-item={p.id}
                  className={`p-3 rounded-xl border transition-all ${
                    isSelected
                      ? 'border-amber-400 bg-amber-50/60 ring-2 ring-amber-400/40 shadow-xs'
                      : isActive
                      ? 'border-[#8D4B00] bg-amber-50/20 ring-1 ring-[#8D4B00]/20 shadow-2xs'
                      : 'border-stone-200 hover:border-stone-300 bg-white shadow-2xs'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    {/* Project Selection Checkbox */}
                    <button
                      type="button"
                      data-testid={`checkbox-project-${p.id}`}
                      onClick={(e) => toggleSelect(p.id, e)}
                      className="mt-0.5 p-0.5 rounded text-stone-400 hover:text-stone-700 cursor-pointer"
                      title={isSelected ? 'Deselect project' : 'Select project'}
                    >
                      {isSelected ? (
                        <CheckSquare className="w-4 h-4 text-[#8D4B00]" />
                      ) : (
                        <Square className="w-4 h-4 text-stone-400" />
                      )}
                    </button>

                    {/* Main Info */}
                    <div
                      className="min-w-0 flex-1 cursor-pointer"
                      onClick={() => toggleSelect(p.id)}
                    >
                      <div className="flex items-center gap-1.5">
                        <Film className="w-3.5 h-3.5 text-stone-400 shrink-0" />
                        <h3 className="font-bold text-xs text-stone-900 truncate" title={p.name}>
                          {p.name}
                        </h3>
                        {isActive && (
                          <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-[#8D4B00] text-white shrink-0">
                            Active
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-2 mt-1.5 text-[11px] text-stone-500 flex-wrap">
                        <span className="font-medium text-stone-700">
                          {stageLabels[p.stage] || `Stage ${p.stage}`}
                        </span>
                        {p.duration ? (
                          <span className="font-mono text-stone-400">
                            • {p.duration.toFixed(1)}s
                          </span>
                        ) : null}
                      </div>
                    </div>

                    {/* Actions & Status */}
                    <div className="flex flex-col items-end gap-1.5 shrink-0">
                      {getStatusBadge(p.status)}

                      <div className="flex items-center gap-1 mt-1">
                        <button
                          type="button"
                          data-testid={`activate-project-${p.id}`}
                          onClick={async () => {
                            await selectProject(p.id);
                            setDrawerOpen(false);
                          }}
                          className={`px-2 py-0.5 text-[11px] font-semibold rounded cursor-pointer transition-colors ${
                            isActive
                              ? 'bg-amber-100 text-[#8D4B00] font-bold'
                              : 'bg-stone-100 hover:bg-stone-200 text-stone-700'
                          }`}
                        >
                          {isActive ? 'Current' : 'Open'}
                        </button>

                        <button
                          type="button"
                          data-testid={`delete-project-${p.id}`}
                          onClick={async () => {
                            if (window.confirm(`Delete project "${p.name}"?`)) {
                              await deleteProjectById(p.id);
                              setSelectedIds((prev) => {
                                const next = new Set(prev);
                                next.delete(p.id);
                                return next;
                              });
                            }
                          }}
                          className="w-6 h-6 rounded flex items-center justify-center text-stone-400 hover:text-rose-600 hover:bg-rose-50 cursor-pointer transition-colors"
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

        {/* Footer / Summary */}
        <div className="px-4 py-2.5 border-t border-stone-200 bg-stone-50/80 flex items-center justify-between text-xs text-stone-500 shrink-0">
          <span>
            {projectsList.length} total {projectsList.length === 1 ? 'project' : 'projects'}
          </span>
          {selectedIds.size > 0 && (
            <span className="font-semibold text-stone-700">
              {selectedIds.size} ready for bulk action
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
