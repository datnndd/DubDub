import React from 'react';
import { useDubDubStore } from '../store';
import { Waves, Video, Mic, BookOpen, FolderOpen, Sparkles } from 'lucide-react';

export const Header: React.FC = () => {
  const currentStep = useDubDubStore((s) => s.currentStep);
  const setStep = useDubDubStore((s) => s.setStep);
  const project = useDubDubStore((s) => s.project);
  const projectsList = useDubDubStore((s) => s.projectsList);
  const drawerOpen = useDubDubStore((s) => s.drawerOpen);
  const setDrawerOpen = useDubDubStore((s) => s.setDrawerOpen);
  const setVoiceManagerDrawerOpen = useDubDubStore((s) => s.setVoiceManagerDrawerOpen);

  return (
    <header className="h-[50px] flex-shrink-0 bg-white border-b border-[#E7E4DC] px-4 flex items-center justify-between gap-4 z-30 shadow-2xs">
      {/* Left: DubDub Branding & Workspace Navigation */}
      <div className="flex items-center gap-3 min-w-0">
        <div
          className="flex items-center gap-2 cursor-pointer"
          onClick={() => setStep(1)}
        >
          <div className="w-8 h-8 rounded-lg bg-amber-500/15 text-[#8D4B00] flex items-center justify-center border border-amber-500/25 shadow-2xs">
            <Waves className="w-4 h-4" />
          </div>
          <div className="flex flex-col leading-none">
            <span className="font-bold text-xs tracking-tight text-stone-900">DubDub</span>
            <span className="text-[10px] text-stone-400 font-medium mt-0.5">Voice &amp; Subtitles Studio</span>
          </div>
        </div>

        <div className="h-4 w-px bg-stone-200" />

        {/* Navigation Tabs */}
        <nav className="flex items-center gap-1 p-0.5 bg-stone-100/80 rounded-lg border border-stone-200/80 text-[11px]">
          <button className="px-2.5 py-1 rounded-md font-bold bg-white text-[#8D4B00] shadow-2xs border border-amber-200/80 flex items-center gap-1 leading-none">
            <Video className="w-3.5 h-3.5 text-[#8D4B00]" />
            <span>Video Dub</span>
          </button>
          <button
            onClick={() => setVoiceManagerDrawerOpen(true)}
            className="px-2.5 py-1 rounded-md font-medium text-stone-600 hover:text-stone-900 transition-colors flex items-center gap-1 leading-none cursor-pointer"
          >
            <Mic className="w-3.5 h-3.5 text-stone-400" />
            <span>Manage Voice</span>
          </button>
          <button className="px-2.5 py-1 rounded-md font-medium text-stone-600 hover:text-stone-900 transition-colors flex items-center gap-1 leading-none">
            <BookOpen className="w-3.5 h-3.5 text-stone-400" />
            <span>Audio Book</span>
          </button>
        </nav>
      </div>

      {/* Center-Right: Active Project Indicator */}
      <div className="hidden lg:flex items-center gap-1.5 text-[11px] text-stone-600">
        <span className="w-2 h-2 rounded-full bg-[#8D4B00]" />
        <span className="font-medium text-stone-700">
          Project: <strong className="text-stone-900">{project.filename}</strong>
        </span>
      </div>

      {/* Right: Projects Drawer, Auto-save status */}
      <div className="flex items-center gap-3 flex-shrink-0">
        <button
          onClick={() => setDrawerOpen(!drawerOpen)}
          data-project-drawer-trigger="true"
          className="px-2.5 py-1 rounded-md font-semibold text-stone-700 hover:text-stone-900 bg-stone-100/90 hover:bg-stone-200/80 border border-stone-200 transition-colors flex items-center gap-1.5 leading-none cursor-pointer shadow-2xs"
          title="Open Projects Drawer"
        >
          <FolderOpen className="w-3.5 h-3.5 text-[#8D4B00]" />
          <span>Projects</span>
          {projectsList?.length > 0 && (
            <span className="px-1.5 py-0.2 bg-amber-100 text-[#8D4B00] rounded-full text-[9px] font-bold">
              {projectsList.length}
            </span>
          )}
        </button>

        <div className="hidden sm:flex items-center gap-1 text-[11px] text-stone-500 font-medium">
          <Sparkles className="w-3 h-3 text-stone-400" />
          <span>Auto-saved {project.lastSaved || 'Just now'}</span>
        </div>

        <div className="flex items-center gap-2 px-2.5 py-1 bg-stone-50 rounded-lg border border-stone-200 shadow-2xs">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 warm-pulse" />
          <span className="font-mono text-[10px] font-semibold text-stone-700">Warm GPU</span>
        </div>
      </div>
    </header>
  );
};
