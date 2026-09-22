import React from 'react';
import { useDubDubStore } from '../store';
import { Loader2, CheckCircle2, AlertCircle, X, Hourglass } from 'lucide-react';

export const FloatingPill: React.FC = () => {
  const activeJob = useDubDubStore((s) => s.activeJob);
  const jobStatus = useDubDubStore((s) => s.jobStatus);
  const jobProgress = useDubDubStore((s) => s.jobProgress);
  const jobMessage = useDubDubStore((s) => s.jobMessage);
  const project = useDubDubStore((s) => s.project);
  const cancelActiveJob = useDubDubStore((s) => s.cancelActiveJob);
  const clearJob = useDubDubStore((s) => s.clearJob);

  if (!activeJob && jobStatus === 'idle') return null;

  const isActive = jobStatus === 'running';
  const isDone = jobStatus === 'completed';
  const isError = jobStatus === 'failed';

  const borderClass = isError
    ? 'border-rose-300 bg-rose-50/95 text-rose-900 shadow-rose-200/50'
    : isDone
    ? 'border-emerald-300 bg-emerald-50/95 text-emerald-900 shadow-emerald-200/50'
    : 'border-amber-300 bg-white/95 text-stone-800 shadow-amber-900/10';

  return (
    <div
      data-floating-pill="true"
      role="status"
      className={`fixed bottom-12 right-6 z-40 flex items-center gap-3 p-2.5 rounded-2xl border shadow-xl backdrop-blur-md transition-all duration-300 ${borderClass} max-w-sm cursor-pointer hover:scale-[1.02]`}
    >
      {/* Icon */}
      <div
        className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 ${
          isActive
            ? 'bg-amber-100 text-[#8D4B00]'
            : isDone
            ? 'bg-emerald-100 text-emerald-700'
            : 'bg-rose-100 text-rose-700'
        }`}
      >
        {isActive ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : isDone ? (
          <CheckCircle2 className="w-4 h-4" />
        ) : isError ? (
          <AlertCircle className="w-4 h-4" />
        ) : (
          <Hourglass className="w-4 h-4" />
        )}
      </div>

      {/* Text & Progress */}
      <div className="flex-1 min-w-0 pr-1">
        <div className="flex items-center justify-between gap-2">
          <span className="font-bold text-[11px] truncate text-stone-900">
            {project.filename || 'Active Project'}
          </span>
        </div>

        <div className="flex items-center justify-between gap-2 mt-0.5 text-[10px] text-stone-600">
          <span className="truncate">{jobMessage || (isActive ? 'Processing...' : jobStatus)}</span>
          {jobProgress != null && isActive && (
            <span className="font-mono font-bold text-[#8D4B00]">{Math.round(jobProgress)}%</span>
          )}
        </div>

        {isActive && (
          <div className="w-full h-1.5 bg-stone-100 rounded-full overflow-hidden mt-1.5 border border-stone-200/60">
            <div
              className={`h-full bg-gradient-to-r from-amber-500 to-[#8D4B00] transition-all duration-300 rounded-full ${
                jobProgress == null ? 'animate-pulse w-2/3' : ''
              }`}
              style={jobProgress != null ? { width: `${jobProgress}%` } : undefined}
            />
          </div>
        )}
      </div>

      {/* Action: Cancel or Dismiss */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          if (isActive) cancelActiveJob();
          else clearJob();
        }}
        className="w-6 h-6 rounded-full hover:bg-black/5 flex items-center justify-center text-stone-400 hover:text-stone-700 cursor-pointer shrink-0"
        title={isActive ? 'Cancel Job' : 'Dismiss'}
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
};
