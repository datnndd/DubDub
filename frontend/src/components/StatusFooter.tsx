import React from 'react';
import { useDubDubStore } from '../store';
import { Play, ArrowRight, Video, CheckCircle2, AlertCircle, Loader2, StopCircle } from 'lucide-react';

export const StatusFooter: React.FC = () => {
  const currentStep = useDubDubStore((s) => s.currentStep);
  const setStep = useDubDubStore((s) => s.setStep);
  const backend = useDubDubStore((s) => s.backend);
  const project = useDubDubStore((s) => s.project);
  const jobStatus = useDubDubStore((s) => s.jobStatus);
  const jobProgress = useDubDubStore((s) => s.jobProgress);
  const jobMessage = useDubDubStore((s) => s.jobMessage);
  const startPrepareJob = useDubDubStore((s) => s.startPrepareJob);
  const cancelActiveJob = useDubDubStore((s) => s.cancelActiveJob);
  const exportEditedVideo = useDubDubStore((s) => s.exportEditedVideo);

  const isBusy = jobStatus === 'running' || backend.status === 'analyzing';
  const isCancellable = jobStatus === 'running';

  const handleAction = () => {
    if (currentStep === 1) {
      if (isCancellable) {
        cancelActiveJob();
      } else {
        startPrepareJob();
      }
    } else if (currentStep === 2) {
      setStep(3);
    } else if (currentStep === 3) {
      setStep(4);
    } else if (currentStep === 4) {
      exportEditedVideo();
    }
  };

  const getActionConfig = () => {
    if (currentStep === 1) {
      if (isCancellable) {
        return {
          text: 'Cancel Processing',
          icon: <StopCircle className="w-3.5 h-3.5" />,
          disabled: false,
          color: 'bg-rose-700 hover:bg-rose-800 text-white',
        };
      }
      if (isBusy) {
        return {
          text: 'Processing ASR…',
          icon: <Loader2 className="w-3.5 h-3.5 animate-spin" />,
          disabled: true,
          color: 'bg-stone-300 text-stone-600',
        };
      }
      return {
        text: 'Start Dub',
        icon: <Play className="w-3.5 h-3.5 fill-current" />,
        disabled: !project.verified,
        color: 'bg-[#8D4B00] hover:bg-[#743D00] text-white',
      };
    }
    if (currentStep === 2) {
      return {
        text: 'Proceed to Voice & Dubbing',
        icon: <ArrowRight className="w-3.5 h-3.5" />,
        disabled: false,
        color: 'bg-[#8D4B00] hover:bg-[#743D00] text-white',
      };
    }
    if (currentStep === 3) {
      return {
        text: 'Proceed to Edit Video',
        icon: <ArrowRight className="w-3.5 h-3.5" />,
        disabled: false,
        color: 'bg-[#8D4B00] hover:bg-[#743D00] text-white',
      };
    }
    return {
      text: 'Render dubbed video',
      icon: <Video className="w-3.5 h-3.5" />,
      disabled: false,
      color: 'bg-[#8D4B00] hover:bg-[#743D00] text-white',
    };
  };

  const actionConfig = getActionConfig();

  return (
    <footer
      data-status-footer="true"
      className="h-[52px] flex-shrink-0 bg-white border-t border-[#E7E4DC] px-4 flex items-center justify-between gap-4 z-30 shadow-xs"
    >
      {/* Left: Live status telemetry */}
      <div className="flex items-center gap-3 min-w-0">
        <div
          className={`w-7 h-7 rounded-lg flex items-center justify-center ${
            jobStatus === 'failed'
              ? 'bg-rose-100 text-rose-700'
              : isBusy
              ? 'bg-amber-100 text-[#8D4B00]'
              : 'bg-emerald-100 text-emerald-700'
          }`}
        >
          {jobStatus === 'failed' ? (
            <AlertCircle className="w-4 h-4" />
          ) : isBusy ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <CheckCircle2 className="w-4 h-4" />
          )}
        </div>

        <div className="flex flex-col min-w-0">
          <div className="font-bold text-xs text-stone-900 truncate">
            {jobMessage || (project.verified ? 'Media verified — ready to process' : 'Choose a video to start')}
          </div>
          <div className="text-[10px] text-stone-500 font-medium">
            {isBusy && jobProgress != null
              ? `Progress: ${jobProgress.toFixed(1)}%`
              : currentStep === 1 && !project.verified
              ? 'Upload a video, then choose languages and backend engines.'
              : 'All engines ready'}
          </div>
        </div>
      </div>

      {/* Right: Primary Action Button */}
      <div className="flex items-center gap-3 flex-shrink-0">
        <button
          onClick={handleAction}
          disabled={actionConfig.disabled}
          className={`px-4 py-2 rounded-lg font-bold text-xs flex items-center gap-1.5 shadow-2xs transition-all cursor-pointer ${
            actionConfig.color
          } ${actionConfig.disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          {actionConfig.icon}
          <span>{actionConfig.text}</span>
        </button>
      </div>
    </footer>
  );
};
