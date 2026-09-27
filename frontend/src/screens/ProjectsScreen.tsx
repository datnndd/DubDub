import React, { useState, useMemo } from 'react';
import { useDubDubStore } from '../store';
import {
  FolderOpen,
  Plus,
  Search,
  X,
  LayoutGrid,
  List,
  Trash2,
  CheckSquare,
  Square,
  MinusSquare,
  Film,
  Clock,
  Calendar,
  AlertTriangle,
  Loader2,
  CheckCircle2,
  ArrowRight,
  ExternalLink,
  Layers,
  ArrowUpDown,
} from 'lucide-react';
import type { ProjectRecord } from '../types/project';

export type SortOption = 'last-modified' | 'date-created' | 'alphabetical';
export type ViewMode = 'grid' | 'table';

export interface ProjectsScreenProps {
  initialViewMode?: ViewMode;
  initialSortBy?: SortOption;
}

export const ProjectsScreen: React.FC<ProjectsScreenProps> = ({
  initialViewMode = 'grid',
  initialSortBy = 'last-modified',
}) => {
  const projectsList = useDubDubStore((s) => s.projectsList);
  const activeProjectId = useDubDubStore((s) => s.activeProjectId);
  const selectProject = useDubDubStore((s) => s.selectProject);
  const createNewProject = useDubDubStore((s) => s.createNewProject);
  const deleteProjectById = useDubDubStore((s) => s.deleteProjectById);
  const deleteProjectsByIds = useDubDubStore((s) => s.deleteProjectsByIds);
  const setActiveView = useDubDubStore((s) => s.setActiveView);

  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<SortOption>(initialSortBy);
  const [viewMode, setViewMode] = useState<ViewMode>(initialViewMode);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  const stageLabels: Record<number, string> = {
    1: '1. Prepare & ASR',
    2: '2. Review Transcript',
    3: '3. Voice Dubbing',
    4: '4. Video Edit & Export',
  };

  const getTimestamp = (p: ProjectRecord, type: 'updated' | 'created'): number => {
    const raw =
      type === 'updated'
        ? p.updated_at || (p as any).updatedAt || p.created_at || (p as any).createdAt
        : p.created_at || (p as any).createdAt || p.updated_at || (p as any).updatedAt;
    if (!raw) return 0;
    const time = new Date(raw).getTime();
    return isNaN(time) ? 0 : time;
  };

  const formatDate = (rawStr?: string): string => {
    if (!rawStr) return '—';
    try {
      const d = new Date(rawStr);
      if (isNaN(d.getTime())) return rawStr;
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return rawStr;
    }
  };

  // 1. Search Filtering
  const filteredProjects = useMemo(() => {
    if (!searchQuery.trim()) return projectsList;
    const q = searchQuery.trim().toLowerCase();
    return projectsList.filter((p) => {
      const name = (p.name || '').toLowerCase();
      const stage = (stageLabels[p.stage] || `Stage ${p.stage}`).toLowerCase();
      const status = (p.status || '').toLowerCase();
      const mediaInfo = (p.media_path || (p as any).mediaId || (p as any).media_id || '').toLowerCase();
      return name.includes(q) || stage.includes(q) || status.includes(q) || mediaInfo.includes(q);
    });
  }, [projectsList, searchQuery]);

  // 2. Chronological & Alphabetical Sorting
  const sortedProjects = useMemo(() => {
    const list = [...filteredProjects];
    if (sortBy === 'last-modified') {
      list.sort(
        (a, b) =>
          getTimestamp(b, 'updated') - getTimestamp(a, 'updated') ||
          (a.name || '').localeCompare(b.name || '')
      );
    } else if (sortBy === 'date-created') {
      list.sort(
        (a, b) =>
          getTimestamp(b, 'created') - getTimestamp(a, 'created') ||
          (a.name || '').localeCompare(b.name || '')
      );
    } else if (sortBy === 'alphabetical') {
      list.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    }
    return list;
  }, [filteredProjects, sortBy]);

  const allFilteredSelected =
    sortedProjects.length > 0 && sortedProjects.every((p) => selectedIds.has(p.id));
  const someFilteredSelected =
    sortedProjects.some((p) => selectedIds.has(p.id)) && !allFilteredSelected;

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
      setSelectedIds(new Set(sortedProjects.map((p) => p.id)));
    }
  };

  const handleOpenProject = async (id: string) => {
    await selectProject(id, true);
  };

  const handleCreateNewProject = async () => {
    setIsCreating(true);
    try {
      await createNewProject();
    } catch (err) {
      console.error('Failed to create new project:', err);
    } finally {
      setIsCreating(false);
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

  const handleDeleteSingle = async (p: ProjectRecord, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (window.confirm(`Delete project "${p.name}"?\nAll associated video, transcription, and dubbing audio will be removed.`)) {
      await deleteProjectById(p.id);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(p.id);
        return next;
      });
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

  const getStageBadge = (stage: number) => {
    switch (stage) {
      case 4:
        return (
          <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
            Stage 4: Edit &amp; Export
          </span>
        );
      case 3:
        return (
          <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-purple-50 text-purple-700 border border-purple-200">
            Stage 3: Voice Dubbing
          </span>
        );
      case 2:
        return (
          <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-200">
            Stage 2: Review Transcript
          </span>
        );
      case 1:
      default:
        return (
          <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-stone-100 text-stone-700 border border-stone-200">
            Stage 1: Prepare &amp; ASR
          </span>
        );
    }
  };

  return (
    <div
      data-screen="projects-screen"
      className="flex-1 w-full h-full flex flex-col bg-[#F9F8F5] overflow-hidden"
    >
      {/* Top Banner / Main Control Bar */}
      <div className="bg-white border-b border-[#E7E4DC] px-6 py-3.5 flex flex-col md:flex-row md:items-center justify-between gap-3 shrink-0 shadow-2xs">
        {/* Title, Badge, and Search */}
        <div className="flex items-center gap-4 flex-1 min-w-0">
          <div className="flex items-center gap-2.5 shrink-0">
            <div className="w-8 h-8 rounded-lg bg-amber-500/15 text-[#8D4B00] flex items-center justify-center border border-amber-500/25 shadow-2xs">
              <FolderOpen className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-bold text-sm text-stone-900 tracking-tight">Project Management</h1>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-[#8D4B00]">
                  {projectsList.length}
                </span>
              </div>
              <p className="text-[10px] text-stone-500 font-medium">
                Organize, open, and batch manage all video dubbing projects
              </p>
            </div>
          </div>

          {/* Search Bar */}
          <div className="relative flex-1 max-w-md min-w-[200px]">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-stone-400 pointer-events-none" />
            <input
              type="text"
              data-testid="projects-search-input"
              placeholder="Search projects by name, stage, or status…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8.5 pr-8 py-1.5 text-xs bg-stone-50 rounded-lg border border-stone-200 focus:bg-white focus:outline-none focus:border-[#8D4B00] transition-colors"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-700 p-0.5"
                title="Clear search"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Right Controls: Sort Dropdown, View Mode Toggle, + New Project */}
        <div className="flex items-center gap-2.5 shrink-0 flex-wrap">
          {/* Chronological Sort Selector */}
          <div className="flex items-center gap-1.5 bg-stone-50 px-2 py-1 rounded-lg border border-stone-200 text-xs">
            <ArrowUpDown className="w-3.5 h-3.5 text-stone-500 shrink-0" />
            <span className="text-stone-500 font-medium hidden sm:inline">Sort:</span>
            <select
              data-testid="projects-sort-select"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortOption)}
              className="bg-transparent text-xs font-semibold text-stone-800 focus:outline-none cursor-pointer"
            >
              <option value="last-modified">Last Modified (Newest first)</option>
              <option value="date-created">Date Created</option>
              <option value="alphabetical">Alphabetical (A-Z)</option>
            </select>
          </div>

          {/* View Mode Toggle: Grid vs Table */}
          <div className="flex items-center p-0.5 bg-stone-100 rounded-lg border border-stone-200 text-stone-600">
            <button
              type="button"
              data-testid="view-mode-grid"
              onClick={() => setViewMode('grid')}
              className={`p-1.5 rounded-md transition-colors cursor-pointer ${
                viewMode === 'grid'
                  ? 'bg-white text-[#8D4B00] shadow-2xs font-bold'
                  : 'text-stone-500 hover:text-stone-900'
              }`}
              title="Card Grid View"
            >
              <LayoutGrid className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              data-testid="view-mode-table"
              onClick={() => setViewMode('table')}
              className={`p-1.5 rounded-md transition-colors cursor-pointer ${
                viewMode === 'table'
                  ? 'bg-white text-[#8D4B00] shadow-2xs font-bold'
                  : 'text-stone-500 hover:text-stone-900'
              }`}
              title="Table List View"
            >
              <List className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* + New Project Button */}
          <button
            type="button"
            data-testid="new-project-btn"
            onClick={handleCreateNewProject}
            disabled={isCreating}
            className="px-3.5 py-1.5 text-xs font-bold rounded-lg bg-[#8D4B00] text-white hover:bg-[#743D00] flex items-center gap-1.5 shadow-2xs cursor-pointer transition-colors disabled:opacity-50"
          >
            {isCreating ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Plus className="w-3.5 h-3.5" />
            )}
            <span>New Project</span>
          </button>
        </div>
      </div>

      {/* Bulk Action & Selection Status Strip */}
      <div className="bg-stone-50/90 border-b border-[#E7E4DC] px-6 py-2 flex items-center justify-between gap-3 text-xs shrink-0">
        <div className="flex items-center gap-3">
          <button
            type="button"
            data-testid="select-all-projects-btn"
            onClick={toggleSelectAll}
            className="flex items-center gap-1.5 font-semibold text-stone-700 hover:text-stone-900 cursor-pointer px-1.5 py-0.5 rounded hover:bg-stone-200/50 transition-colors"
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
                : `Select All (${sortedProjects.length})`}
            </span>
          </button>

          {selectedIds.size > 0 && (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-[#8D4B00]">
              {selectedIds.size} selected
            </span>
          )}
        </div>

        {selectedIds.size > 0 && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              data-testid="clear-selection-btn"
              onClick={() => setSelectedIds(new Set())}
              className="px-2.5 py-1 text-[11px] font-medium text-stone-600 hover:text-stone-900 hover:bg-stone-200/60 rounded cursor-pointer transition-colors"
            >
              Clear selection
            </button>
            <button
              type="button"
              data-testid="bulk-delete-btn"
              onClick={() => setConfirmDeleteOpen(true)}
              className="px-3 py-1 text-[11px] font-bold bg-rose-600 hover:bg-rose-700 text-white rounded-md flex items-center gap-1.5 cursor-pointer transition-colors shadow-2xs"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Delete Selected ({selectedIds.size})</span>
            </button>
          </div>
        )}
      </div>

      {/* Confirmation Modal for Bulk Deletion */}
      {confirmDeleteOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4 animate-fade-in">
          <div className="w-full max-w-md bg-white rounded-xl shadow-2xl border border-stone-200 overflow-hidden">
            <div className="p-4 bg-rose-50 border-b border-rose-100 flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-rose-100 text-rose-700 flex items-center justify-center shrink-0 mt-0.5">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-sm text-stone-900">
                  Delete {selectedIds.size} {selectedIds.size === 1 ? 'Project' : 'Projects'}?
                </h3>
                <p className="text-xs text-stone-600 mt-1">
                  This action is permanent. All transcribed segments, AI dubbing audio files, and exported videos for the selected projects will be deleted.
                </p>
              </div>
            </div>
            <div className="p-3 bg-stone-50 flex items-center justify-end gap-2 border-t border-stone-200">
              <button
                type="button"
                onClick={() => setConfirmDeleteOpen(false)}
                disabled={isDeleting}
                className="px-3 py-1.5 rounded-lg border border-stone-200 text-xs font-semibold text-stone-700 hover:bg-stone-100 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                data-testid="confirm-bulk-delete-btn"
                onClick={handleBulkDelete}
                disabled={isDeleting}
                className="px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold flex items-center gap-1.5 shadow-2xs cursor-pointer disabled:opacity-50"
              >
                {isDeleting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Deleting…</span>
                  </>
                ) : (
                  <>
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Confirm Delete ({selectedIds.size})</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Content Area: Card Grid or Table List */}
      <div className="flex-1 overflow-y-auto p-6">
        {sortedProjects.length === 0 ? (
          <div className="h-96 flex flex-col items-center justify-center text-center p-8 max-w-md mx-auto">
            <div className="w-16 h-16 rounded-2xl bg-amber-500/10 text-[#8D4B00] flex items-center justify-center mb-4 border border-amber-500/20 shadow-2xs">
              <Film className="w-8 h-8" />
            </div>
            <h3 className="font-bold text-sm text-stone-900 mb-1">
              {searchQuery ? 'No matching projects found' : 'No projects yet'}
            </h3>
            <p className="text-xs text-stone-500 mb-5 leading-relaxed">
              {searchQuery
                ? `No projects matched "${searchQuery}". Try searching for another name, stage, or status.`
                : 'Get started by creating a new video dubbing project. You can upload media, generate subtitles, and clone custom voices.'}
            </p>
            {searchQuery ? (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="px-3 py-1.5 text-xs font-semibold text-[#8D4B00] bg-amber-50 hover:bg-amber-100 rounded-lg border border-amber-200 transition-colors cursor-pointer"
              >
                Clear Search Filter
              </button>
            ) : (
              <button
                type="button"
                onClick={handleCreateNewProject}
                className="px-4 py-2 text-xs font-bold bg-[#8D4B00] hover:bg-[#743D00] text-white rounded-lg flex items-center gap-1.5 shadow-sm transition-colors cursor-pointer"
              >
                <Plus className="w-4 h-4" />
                <span>Create First Project</span>
              </button>
            )}
          </div>
        ) : viewMode === 'grid' ? (
          /* Visual Card Grid View */
          <div
            data-testid="projects-grid-view"
            className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4"
          >
            {sortedProjects.map((p) => {
              const isActive = p.id === activeProjectId;
              const isSelected = selectedIds.has(p.id);
              const updatedStr = formatDate(p.updated_at || (p as any).updatedAt);

              return (
                <div
                  key={p.id}
                  data-project-card={p.id}
                  data-project-item={p.id}
                  onClick={() => handleOpenProject(p.id)}
                  className={`group rounded-xl border flex flex-col bg-white shadow-2xs transition-all cursor-pointer relative overflow-hidden ${
                    isSelected
                      ? 'border-amber-400 ring-2 ring-amber-400/40 bg-amber-50/30'
                      : isActive
                      ? 'border-[#8D4B00] ring-1 ring-[#8D4B00]/30 bg-amber-50/10'
                      : 'border-stone-200 hover:border-amber-300 hover:shadow-xs'
                  }`}
                >
                  {/* Thumbnail / Header Area */}
                  <div className="h-32 bg-stone-100 border-b border-stone-200 relative flex items-center justify-center overflow-hidden group-hover:bg-stone-200/70 transition-colors">
                    <Film className="w-10 h-10 text-stone-300 group-hover:scale-110 transition-transform" />

                    {/* Top Left Selection Checkbox */}
                    <button
                      type="button"
                      data-testid={`checkbox-project-${p.id}`}
                      onClick={(e) => toggleSelect(p.id, e)}
                      className="absolute top-2.5 left-2.5 p-1 rounded-md bg-white/90 shadow-2xs hover:bg-white text-stone-500 hover:text-stone-900 cursor-pointer transition-colors z-10"
                      title={isSelected ? 'Deselect project' : 'Select project'}
                    >
                      {isSelected ? (
                        <CheckSquare className="w-4 h-4 text-[#8D4B00]" />
                      ) : (
                        <Square className="w-4 h-4 text-stone-400" />
                      )}
                    </button>

                    {/* Top Right Active / Status Badge */}
                    <div className="absolute top-2.5 right-2.5 flex items-center gap-1 z-10">
                      {isActive && (
                        <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-[#8D4B00] text-white shadow-2xs">
                          Active
                        </span>
                      )}
                      {getStatusBadge(p.status)}
                    </div>

                    {/* Bottom Duration Badge */}
                    {p.duration ? (
                      <span className="absolute bottom-2 right-2.5 px-1.5 py-0.5 bg-black/60 backdrop-blur-xs text-white rounded text-[10px] font-mono font-medium">
                        {p.duration.toFixed(1)}s
                      </span>
                    ) : null}
                  </div>

                  {/* Card Body */}
                  <div className="p-3.5 flex-1 flex flex-col justify-between space-y-3">
                    <div className="space-y-1.5">
                      <div className="flex items-start justify-between gap-1.5">
                        <h2
                          className="font-bold text-xs text-stone-900 truncate flex-1"
                          title={p.name}
                        >
                          {p.name}
                        </h2>
                      </div>
                      <div>{getStageBadge(p.stage)}</div>
                    </div>

                    {/* Timestamps */}
                    <div className="flex items-center justify-between text-[11px] text-stone-400 pt-2 border-t border-stone-100">
                      <div className="flex items-center gap-1 text-stone-500">
                        <Clock className="w-3 h-3 text-stone-400" />
                        <span>{updatedStr}</span>
                      </div>
                    </div>

                    {/* Quick Action Footer */}
                    <div className="pt-2 flex items-center justify-between gap-2">
                      <button
                        type="button"
                        data-testid={`activate-project-${p.id}`}
                        onClick={async (e) => {
                          e.stopPropagation();
                          await handleOpenProject(p.id);
                        }}
                        className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 cursor-pointer transition-colors shadow-2xs ${
                          isActive
                            ? 'bg-amber-100 text-[#8D4B00] hover:bg-amber-200'
                            : 'bg-[#8D4B00] text-white hover:bg-[#743D00]'
                        }`}
                      >
                        <span>{isActive ? 'Continue Working' : 'Open Project'}</span>
                        <ArrowRight className="w-3 h-3" />
                      </button>

                      <button
                        type="button"
                        data-testid={`delete-project-${p.id}`}
                        onClick={(e) => handleDeleteSingle(p, e)}
                        className="w-8 h-8 rounded-lg border border-stone-200 flex items-center justify-center text-stone-400 hover:text-rose-600 hover:bg-rose-50 hover:border-rose-200 cursor-pointer transition-colors"
                        title="Delete Project"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          /* Compact Table List View */
          <div
            data-testid="projects-table-view"
            className="bg-white rounded-xl border border-stone-200 shadow-2xs overflow-hidden"
          >
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-stone-50 border-b border-stone-200 text-stone-600 text-[11px] font-bold uppercase tracking-wider">
                  <th className="py-2.5 pl-4 pr-2 w-10">
                    <button
                      type="button"
                      onClick={toggleSelectAll}
                      className="p-1 rounded text-stone-400 hover:text-stone-700"
                    >
                      {allFilteredSelected ? (
                        <CheckSquare className="w-4 h-4 text-[#8D4B00]" />
                      ) : (
                        <Square className="w-4 h-4" />
                      )}
                    </button>
                  </th>
                  <th className="py-2.5 px-3">Project Name</th>
                  <th className="py-2.5 px-3">Workflow Stage</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Duration</th>
                  <th className="py-2.5 px-3">Last Modified</th>
                  <th className="py-2.5 pr-4 pl-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {sortedProjects.map((p) => {
                  const isActive = p.id === activeProjectId;
                  const isSelected = selectedIds.has(p.id);

                  return (
                    <tr
                      key={p.id}
                      data-project-item={p.id}
                      onClick={() => handleOpenProject(p.id)}
                      className={`hover:bg-amber-50/40 cursor-pointer transition-colors ${
                        isSelected
                          ? 'bg-amber-50/60'
                          : isActive
                          ? 'bg-amber-50/20'
                          : ''
                      }`}
                    >
                      <td className="py-2.5 pl-4 pr-2">
                        <button
                          type="button"
                          data-testid={`checkbox-project-${p.id}`}
                          onClick={(e) => toggleSelect(p.id, e)}
                          className="p-1 rounded text-stone-400 hover:text-stone-700"
                        >
                          {isSelected ? (
                            <CheckSquare className="w-4 h-4 text-[#8D4B00]" />
                          ) : (
                            <Square className="w-4 h-4 text-stone-400" />
                          )}
                        </button>
                      </td>
                      <td className="py-2.5 px-3 min-w-[200px]">
                        <div className="flex items-center gap-2">
                          <Film className="w-3.5 h-3.5 text-stone-400 shrink-0" />
                          <span className="font-bold text-stone-900 truncate" title={p.name}>
                            {p.name}
                          </span>
                          {isActive && (
                            <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-[#8D4B00] text-white shrink-0">
                              Active
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-2.5 px-3 whitespace-nowrap">
                        {getStageBadge(p.stage)}
                      </td>
                      <td className="py-2.5 px-3 whitespace-nowrap">
                        {getStatusBadge(p.status)}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-stone-500 whitespace-nowrap">
                        {p.duration ? `${p.duration.toFixed(1)}s` : '—'}
                      </td>
                      <td className="py-2.5 px-3 text-stone-500 whitespace-nowrap">
                        {formatDate(p.updated_at || (p as any).updatedAt)}
                      </td>
                      <td className="py-2.5 pr-4 pl-3 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            data-testid={`activate-project-${p.id}`}
                            onClick={async (e) => {
                              e.stopPropagation();
                              await handleOpenProject(p.id);
                            }}
                            className={`px-2.5 py-1 text-xs font-semibold rounded-md cursor-pointer transition-colors shadow-2xs ${
                              isActive
                                ? 'bg-amber-100 text-[#8D4B00] font-bold'
                                : 'bg-[#8D4B00] text-white hover:bg-[#743D00]'
                            }`}
                          >
                            {isActive ? 'Current' : 'Open'}
                          </button>
                          <button
                            type="button"
                            data-testid={`delete-project-${p.id}`}
                            onClick={(e) => handleDeleteSingle(p, e)}
                            className="p-1 rounded hover:bg-rose-50 text-stone-400 hover:text-rose-600 transition-colors cursor-pointer"
                            title="Delete project"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Status Footer info bar */}
      <div className="h-9 px-6 bg-white border-t border-[#E7E4DC] flex items-center justify-between text-xs text-stone-500 shrink-0">
        <div className="flex items-center gap-3">
          <span>
            Total: <strong>{projectsList.length}</strong> {projectsList.length === 1 ? 'project' : 'projects'}
          </span>
          {searchQuery && (
            <span className="text-amber-800 font-medium">
              (Filtered: {sortedProjects.length} matches)
            </span>
          )}
        </div>
        {selectedIds.size > 0 && (
          <span className="font-semibold text-stone-700">
            {selectedIds.size} ready for bulk deletion
          </span>
        )}
      </div>
    </div>
  );
};
