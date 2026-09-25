import React, { useState } from 'react';
import {
  FolderOpen,
  HardDrive,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Loader2,
  RefreshCw,
  Check,
  ShieldAlert,
} from 'lucide-react';
import { StorageMetrics, updateStorageSettings, cleanTempCache } from '../../../api/settingsApi';
import { formatBytes } from '../../../store/prepareSlice';

interface StorageTabProps {
  storage: StorageMetrics;
  onRefresh: () => Promise<void>;
}

export const StorageTab: React.FC<StorageTabProps> = ({ storage, onRefresh }) => {
  const [pathsState, setPathsState] = useState(storage.paths);
  const [saving, setSaving] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  React.useEffect(() => {
    setPathsState(storage.paths);
  }, [storage.paths]);

  const usage = storage.usage;
  const diskTotal = usage.disk_total_bytes || 1;
  const diskUsed = usage.disk_used_bytes || 0;
  const diskFree = usage.disk_free_bytes || 0;
  const usedPercent = Math.min(100, Math.round((diskUsed / diskTotal) * 100));

  const handleSavePaths = async () => {
    setSaving(true);
    setFeedback(null);
    try {
      await updateStorageSettings(pathsState);
      await onRefresh();
      setFeedback({ type: 'success', message: 'Storage paths validated and saved successfully' });
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message || 'Failed to update storage paths' });
    } finally {
      setSaving(false);
    }
  };

  const handleCleanTemp = async () => {
    setCleaning(true);
    setFeedback(null);
    try {
      const res = await cleanTempCache();
      await onRefresh();
      const freed = formatBytes(res.cleaned_bytes);
      setFeedback({
        type: 'success',
        message: `Successfully cleaned ${freed} across ${res.cleaned_files} temporary files. Active jobs were preserved.`,
      });
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message || 'Failed to clean temporary cache' });
    } finally {
      setCleaning(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* Disk Usage Banner */}
      <div className="bg-white rounded-xl border border-stone-200 p-4 shadow-2xs">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <HardDrive className="w-4 h-4 text-[#8D4B00]" />
            <h4 className="font-bold text-xs text-stone-900">Host Storage Space</h4>
          </div>
          <span className="text-[11px] font-semibold text-stone-600">
            {formatBytes(diskUsed)} used of {formatBytes(diskTotal)} ({usedPercent}%)
          </span>
        </div>

        {/* Progress Bar */}
        <div className="w-full h-2.5 bg-stone-100 rounded-full overflow-hidden border border-stone-200">
          <div
            className={`h-full transition-all rounded-full ${
              usedPercent > 90 ? 'bg-rose-500' : usedPercent > 75 ? 'bg-amber-500' : 'bg-emerald-500'
            }`}
            style={{ width: `${usedPercent}%` }}
          />
        </div>

        <div className="flex items-center justify-between text-[10px] text-stone-500 font-medium mt-2">
          <span>Free: {formatBytes(diskFree)}</span>
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            <span>Optimal Headroom</span>
          </span>
        </div>
      </div>

      {/* Directory Usage Breakdown */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-stone-50 rounded-xl border border-stone-200 p-3">
          <span className="text-[10px] text-stone-500 font-semibold block mb-0.5">Projects Output</span>
          <strong className="text-xs font-bold text-stone-900">{formatBytes(usage.output_dir_bytes)}</strong>
        </div>
        <div className="bg-stone-50 rounded-xl border border-stone-200 p-3">
          <span className="text-[10px] text-stone-500 font-semibold block mb-0.5">Media Uploads</span>
          <strong className="text-xs font-bold text-stone-900">{formatBytes(usage.uploads_dir_bytes)}</strong>
        </div>
        <div className="bg-stone-50 rounded-xl border border-stone-200 p-3">
          <span className="text-[10px] text-stone-500 font-semibold block mb-0.5">AI Models Cache</span>
          <strong className="text-xs font-bold text-stone-900">{formatBytes(usage.models_dir_bytes)}</strong>
        </div>
        <div className="bg-stone-50 rounded-xl border border-stone-200 p-3 flex flex-col justify-between">
          <div>
            <span className="text-[10px] text-stone-500 font-semibold block mb-0.5">Temp Working Files</span>
            <strong className="text-xs font-bold text-stone-900">{formatBytes(usage.temp_dir_bytes)}</strong>
          </div>
        </div>
      </div>

      {/* Storage Path Inputs */}
      <div className="bg-white rounded-xl border border-stone-200 p-4 shadow-2xs space-y-3.5">
        <div className="flex items-center justify-between border-b border-stone-100 pb-2">
          <div className="flex items-center gap-2">
            <FolderOpen className="w-4 h-4 text-[#8D4B00]" />
            <h4 className="font-bold text-xs text-stone-900">Custom Storage Directories</h4>
          </div>
          <span className="text-[10px] text-stone-400 font-medium">All paths must be absolute</span>
        </div>

        <div className="space-y-3 text-xs">
          <div>
            <label className="text-[10px] font-semibold text-stone-600 block mb-1">
              Projects &amp; Render Output Directory
            </label>
            <input
              type="text"
              value={pathsState.output_dir}
              onChange={(e) => setPathsState((p) => ({ ...p, output_dir: e.target.value }))}
              className="w-full text-xs p-2 bg-stone-50 rounded-lg border border-stone-200 focus:bg-white focus:outline-none focus:border-amber-400 font-mono"
            />
          </div>

          <div>
            <label className="text-[10px] font-semibold text-stone-600 block mb-1">
              Incoming Media Uploads Staging
            </label>
            <input
              type="text"
              value={pathsState.uploads_dir}
              onChange={(e) => setPathsState((p) => ({ ...p, uploads_dir: e.target.value }))}
              className="w-full text-xs p-2 bg-stone-50 rounded-lg border border-stone-200 focus:bg-white focus:outline-none focus:border-amber-400 font-mono"
            />
          </div>

          <div>
            <label className="text-[10px] font-semibold text-stone-600 block mb-1">
              AI Models Storage Directory
            </label>
            <input
              type="text"
              value={pathsState.models_dir}
              onChange={(e) => setPathsState((p) => ({ ...p, models_dir: e.target.value }))}
              className="w-full text-xs p-2 bg-stone-50 rounded-lg border border-stone-200 focus:bg-white focus:outline-none focus:border-amber-400 font-mono"
            />
          </div>

          <div>
            <label className="text-[10px] font-semibold text-stone-600 block mb-1">
              Temporary Audio &amp; Subtitle Working Directory
            </label>
            <input
              type="text"
              value={pathsState.temp_dir}
              onChange={(e) => setPathsState((p) => ({ ...p, temp_dir: e.target.value }))}
              className="w-full text-xs p-2 bg-stone-50 rounded-lg border border-stone-200 focus:bg-white focus:outline-none focus:border-amber-400 font-mono"
            />
          </div>
        </div>

        {/* Feedback Alert */}
        {feedback && (
          <div
            className={`p-2.5 rounded-lg text-[11px] flex items-start gap-2 ${
              feedback.type === 'success'
                ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                : 'bg-rose-50 text-rose-800 border border-rose-200'
            }`}
          >
            {feedback.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            )}
            <span className="leading-tight">{feedback.message}</span>
          </div>
        )}

        <div className="flex items-center justify-between pt-2 border-t border-stone-100">
          {/* Clean Temp Button */}
          <button
            type="button"
            onClick={handleCleanTemp}
            disabled={cleaning}
            className="px-3 py-1.5 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs font-semibold flex items-center gap-1.5 border border-rose-200 disabled:opacity-50 cursor-pointer transition-colors"
          >
            {cleaning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
            <span>Clear Temp Cache</span>
          </button>

          {/* Save Button */}
          <button
            type="button"
            onClick={handleSavePaths}
            disabled={saving}
            className="px-4 py-1.5 rounded-lg bg-[#8D4B00] hover:bg-[#743D00] text-white text-xs font-bold flex items-center gap-1.5 disabled:opacity-50 cursor-pointer shadow-2xs transition-colors"
          >
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
            <span>Save Paths</span>
          </button>
        </div>
      </div>
    </div>
  );
};
