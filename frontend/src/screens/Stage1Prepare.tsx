import React, { useRef, useState } from 'react';
import { useDubDubStore } from '../store';
import {
  Upload,
  Film,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Settings2,
  Sliders,
  Volume2,
  Mic,
  Key,
  X,
  Check,
} from 'lucide-react';
import { saveAsrSettings } from '../api/settings';

export const Stage1Prepare: React.FC = () => {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [settingsModalOpen, setSettingsModalOpen] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [savingKey, setSavingKey] = useState(false);
  const [keySavedMsg, setKeySavedMsg] = useState<string | null>(null);

  const project = useDubDubStore((s) => s.project);
  const languages = useDubDubStore((s) => s.languages);
  const engines = useDubDubStore((s) => s.engines);
  const backend = useDubDubStore((s) => s.backend);
  const jobStatus = useDubDubStore((s) => s.jobStatus);
  const jobProgress = useDubDubStore((s) => s.jobProgress);
  const jobStage = useDubDubStore((s) => s.jobStage);
  const jobMessage = useDubDubStore((s) => s.jobMessage);
  const elapsedSeconds = useDubDubStore((s) => s.elapsedSeconds);
  const selectMedia = useDubDubStore((s) => s.selectMedia);
  const updateSourceLanguage = useDubDubStore((s) => s.updateSourceLanguage);
  const updateTargetLanguage = useDubDubStore((s) => s.updateTargetLanguage);
  const updateAsrProvider = useDubDubStore((s) => s.updateAsrProvider);
  const updateEngineConfig = useDubDubStore((s) => s.updateEngineConfig);

  const options = backend.options;
  const isAnalyzing = backend.status === 'analyzing';
  const isRunning = jobStatus === 'running';
  const isFailed = jobStatus === 'failed';

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      selectMedia(file);
    }
  };

  const selectedProvider = options.asrProviders?.find(
    (item: any) => item.recognType === Number(backend.config.recognType)
  ) || options.asrProviders?.[0] || { id: 'deepgram', label: 'Deepgram', models: ['nova-3'], recognType: 1 };

  const handleSaveApiKey = async () => {
    if (!apiKeyInput.trim()) return;
    setSavingKey(true);
    setKeySavedMsg(null);
    try {
      await saveAsrSettings(String(selectedProvider.id || ''), apiKeyInput.trim());
      selectedProvider.configured = true;
      setKeySavedMsg('API key saved successfully!');
      setTimeout(() => {
        setSettingsModalOpen(false);
        setKeySavedMsg(null);
      }, 1200);
    } catch (err: any) {
      setKeySavedMsg(`Error: ${err.message}`);
    } finally {
      setSavingKey(false);
    }
  };

  return (
    <div className="flex-1 min-h-0 w-full p-2.5 flex flex-col gap-2.5 overflow-hidden">
      <input
        ref={fileInputRef}
        type="file"
        accept="video/*,audio/*"
        className="hidden"
        onChange={handleFileChange}
      />

      {/* TOP MEDIA STRIP: Video Preview & Metadata */}
      <section className="flex-1 min-h-0 w-full grid grid-cols-12 gap-2.5 overflow-hidden">
        {/* LEFT: Video Snapshot (7-8 cols) */}
        <div className="col-span-12 md:col-span-7 lg:col-span-8 h-full bg-white rounded-xl border border-[#E7E4DC] shadow-xs flex flex-col min-h-0 overflow-hidden">
          <div className="h-7 px-3 border-b border-[#E7E4DC] flex items-center justify-between bg-[#FAF9F6] shrink-0">
            <div className="flex items-center gap-2">
              <Film className="w-3.5 h-3.5 text-[#8D4B00]" />
              <span className="text-xs font-bold text-stone-900">Source Video &amp; Sound Canvas</span>
              <span
                onClick={() => fileInputRef.current?.click()}
                className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-amber-100 text-[#8D4B00] uppercase tracking-wide cursor-pointer hover:bg-amber-200 transition-colors"
              >
                {project.verified ? 'Media Verified' : 'Awaiting Media'}
              </span>
            </div>
            <div className="flex items-center gap-2 font-mono text-[10px] text-stone-500">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              <span>{project.hasAudio ? `Audio: ${project.audioCodec}` : 'Audio stream not verified'}</span>
            </div>
          </div>

          <div
            className={`relative flex-1 min-h-0 bg-neutral-950 flex items-center justify-center overflow-hidden group ${
              project.previewUrl ? '' : 'cursor-pointer hover:bg-neutral-900 transition-colors'
            }`}
            onClick={() => {
              if (!project.previewUrl) fileInputRef.current?.click();
            }}
          >
            {project.previewUrl ? (
              <video
                data-source-preview="true"
                className="w-full h-full object-contain bg-black"
                src={project.previewUrl}
                controls
                preload="metadata"
              />
            ) : (
              <div className="flex flex-col items-center justify-center gap-2.5 p-6 text-center select-none">
                <div className="w-12 h-12 rounded-xl bg-stone-800/80 border border-stone-700/60 flex items-center justify-center text-amber-400 group-hover:scale-105 group-hover:bg-stone-800 group-hover:text-amber-300 transition-all shadow-md">
                  <Upload className="w-6 h-6" />
                </div>
                <div className="flex flex-col items-center gap-0.5">
                  <span className="text-xs font-bold text-stone-200 group-hover:text-white transition-colors">
                    Click to select or upload a video
                  </span>
                  <span className="text-[10px] text-stone-400">MP4, MKV, MOV, WebM (up to 4K supported)</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT: Ingest Diagnostics & Stream Card (4-5 cols) */}
        <div className="col-span-12 md:col-span-5 lg:col-span-4 h-full bg-white rounded-xl border border-[#E7E4DC] shadow-xs flex flex-col min-h-0 overflow-hidden">
          <div className="h-7 px-3 border-b border-[#E7E4DC] flex items-center justify-between bg-[#FAF9F6] shrink-0">
            <div className="flex items-center gap-1.5 font-bold text-xs text-stone-900">
              <Sliders className="w-3.5 h-3.5 text-[#8D4B00]" />
              <span>Media Stream Diagnostics</span>
            </div>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="px-2 py-0.5 rounded text-[10px] font-semibold bg-stone-100 hover:bg-stone-200 text-stone-700 transition-colors cursor-pointer"
            >
              Replace
            </button>
          </div>

          <div className="p-3 flex-1 overflow-y-auto flex flex-col gap-2.5">
            {/* Live ASR Progress Card */}
            {isRunning && (
              <div
                data-asr-progress="true"
                className="p-2.5 rounded-lg bg-amber-50/90 border border-amber-300 text-xs text-amber-950 flex flex-col gap-1.5 shadow-xs"
              >
                <div className="flex items-center justify-between font-bold text-[11px] text-[#8D4B00]">
                  <span className="flex items-center gap-1.5">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>ASR Stage: {jobStage || 'Processing'}</span>
                  </span>
                  <div className="flex items-center gap-1.5 font-mono text-[10px]">
                    <span className="px-1.5 py-0.5 rounded bg-amber-100 text-[#8D4B00] font-semibold">
                      ⏱️ {elapsedSeconds}s
                    </span>
                    <span>{jobProgress != null ? `${jobProgress.toFixed(0)}%` : 'Running'}</span>
                  </div>
                </div>
                <div className="w-full bg-amber-200/60 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-[#8D4B00] h-full transition-all duration-300 rounded-full"
                    style={{ width: `${jobProgress != null ? Math.min(100, Math.max(5, jobProgress)) : 25}%` }}
                  />
                </div>
                <div className="text-[10px] text-stone-600 truncate font-mono">
                  {jobMessage || 'Extracting audio & executing speech models...'}
                </div>
              </div>
            )}

            {/* Error Banner */}
            {isFailed && (
              <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-300 text-xs text-rose-900 flex items-start gap-2 shadow-xs">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <div className="font-bold text-[11px] text-rose-800">Processing Error</div>
                  <div className="text-[10px] text-rose-700 mt-0.5">{jobMessage}</div>
                  {selectedProvider.requiresSettings && !selectedProvider.configured && (
                    <button
                      onClick={() => setSettingsModalOpen(true)}
                      className="mt-1.5 px-2 py-0.5 bg-rose-700 text-white rounded text-[10px] font-bold hover:bg-rose-800 cursor-pointer"
                    >
                      Configure {selectedProvider.label} API Key
                    </button>
                  )}
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-2 text-[11px]">
              <div className="p-2 rounded-lg bg-stone-50 border border-stone-200/80">
                <span className="text-[10px] text-stone-400 font-medium block">Resolution</span>
                <span className="font-mono font-bold text-stone-900">{project.resolution}</span>
              </div>
              <div className="p-2 rounded-lg bg-stone-50 border border-stone-200/80">
                <span className="text-[10px] text-stone-400 font-medium block">Frame Rate</span>
                <span className="font-mono font-bold text-stone-900">{project.fps}</span>
              </div>
              <div className="p-2 rounded-lg bg-stone-50 border border-stone-200/80">
                <span className="text-[10px] text-stone-400 font-medium block">Duration</span>
                <span className="font-mono font-bold text-stone-900">{project.duration}</span>
              </div>
              <div className="p-2 rounded-lg bg-stone-50 border border-stone-200/80">
                <span className="text-[10px] text-stone-400 font-medium block">Container Format</span>
                <span className="font-mono font-bold text-stone-900">{project.format}</span>
              </div>
            </div>

            <div className="p-2.5 rounded-lg bg-stone-50 border border-stone-200/80 flex flex-col gap-1 text-[11px]">
              <div className="flex items-center justify-between">
                <span className="text-stone-500 font-medium">Video Codec:</span>
                <span className="font-mono font-bold text-stone-800">{project.videoCodec}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-stone-500 font-medium">Audio Codec:</span>
                <span className="font-mono font-bold text-stone-800">{project.audioCodec}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-stone-500 font-medium">File Size:</span>
                <span className="font-mono font-bold text-stone-800">{project.fileSize}</span>
              </div>
            </div>

            {isAnalyzing && (
              <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-[11px] text-amber-900 flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-[#8D4B00]" />
                <span>Uploading and inspecting source media…</span>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* BOTTOM CONFIGURATION DECK: Languages, ASR, Diarization */}
      <section className="h-[220px] shrink-0 w-full grid grid-cols-12 gap-2.5 overflow-hidden">
        {/* Languages & Timing (4 cols) */}
        <div className="col-span-12 md:col-span-4 h-full bg-white rounded-xl border border-[#E7E4DC] p-3 shadow-xs flex flex-col justify-between overflow-hidden">
          <div className="flex items-center gap-1.5 font-bold text-xs text-stone-900 mb-2">
            <span className="text-[#8D4B00]">🌐</span>
            <span>Language &amp; Timing</span>
          </div>

          <div className="space-y-2 flex-1">
            <div>
              <label className="text-[10px] text-stone-500 font-semibold block mb-0.5">Source Language</label>
              <select
                value={languages.source.code}
                onChange={(e) => {
                  const opt = options.languages?.find((l: any) => l.code === e.target.value);
                  updateSourceLanguage(e.target.value, opt?.name || e.target.value);
                }}
                className="w-full text-xs font-semibold p-1.5 bg-stone-50 rounded-lg border border-stone-200"
              >
                {(options.languages || []).map((l: any) => (
                  <option key={l.code} value={l.code}>
                    {l.name} ({l.code})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-[10px] text-stone-500 font-semibold block mb-0.5">Target Language</label>
              <select
                value={languages.target.code}
                onChange={(e) => {
                  const opt = options.languages?.find((l: any) => l.code === e.target.value);
                  updateTargetLanguage(e.target.value, opt?.name || e.target.value);
                }}
                className="w-full text-xs font-semibold p-1.5 bg-stone-50 rounded-lg border border-stone-200"
              >
                {(options.languages || []).map((l: any) => (
                  <option key={l.code} value={l.code}>
                    {l.name} ({l.code})
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* ASR Speech Recognition Engine (4 cols) */}
        <div className="col-span-12 md:col-span-4 h-full bg-white rounded-xl border border-[#E7E4DC] p-3 shadow-xs flex flex-col justify-between overflow-hidden">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5 font-bold text-xs text-stone-900">
              <Mic className="w-3.5 h-3.5 text-[#8D4B00]" />
              <span>ASR Engine</span>
            </div>
            {selectedProvider.requiresSettings && (
              <button
                type="button"
                onClick={() => setSettingsModalOpen(true)}
                className={`px-2 py-0.5 rounded text-[9px] font-bold flex items-center gap-1 cursor-pointer transition-colors ${
                  selectedProvider.configured
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : 'bg-amber-100 text-[#8D4B00] border border-amber-300 animate-pulse'
                }`}
              >
                <Key className="w-2.5 h-2.5" />
                <span>{selectedProvider.configured ? 'Key Set' : 'Key Needed'}</span>
              </button>
            )}
          </div>

          <div className="space-y-2 flex-1">
            <div>
              <label className="text-[10px] text-stone-500 font-semibold block mb-0.5">Provider</label>
              <select
                value={backend.config.recognType}
                onChange={(e) => {
                  const p = options.asrProviders?.find((x: any) => x.recognType === Number(e.target.value));
                  updateAsrProvider(Number(e.target.value), p?.models?.[0] || 'default');
                }}
                className="w-full text-xs font-semibold p-1.5 bg-stone-50 rounded-lg border border-stone-200"
              >
                {(options.asrProviders || []).map((p: any) => (
                  <option key={p.recognType} value={p.recognType}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-[10px] text-stone-500 font-semibold block mb-0.5">Model</label>
              <select
                value={backend.config.modelName}
                onChange={(e) => updateAsrProvider(backend.config.recognType, e.target.value)}
                className="w-full text-xs font-semibold p-1.5 bg-stone-50 rounded-lg border border-stone-200"
              >
                {(selectedProvider.models || []).map((m: string) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Diarization & Audio Enhancement (4 cols) */}
        <div className="col-span-12 md:col-span-4 h-full bg-white rounded-xl border border-[#E7E4DC] p-3 shadow-xs flex flex-col justify-between overflow-hidden">
          <div className="flex items-center gap-1.5 font-bold text-xs text-stone-900 mb-2">
            <Volume2 className="w-3.5 h-3.5 text-[#8D4B00]" />
            <span>Diarization &amp; Enhancements</span>
          </div>

          <div className="space-y-2.5 flex-1">
            <label className="flex items-center justify-between text-xs cursor-pointer p-1.5 rounded-lg bg-stone-50 border border-stone-200">
              <span className="font-semibold text-stone-800">Speaker Diarization</span>
              <input
                type="checkbox"
                checked={engines.speakerDiarization}
                onChange={(e) => updateEngineConfig('speakerDiarization', e.target.checked)}
                className="rounded text-[#8D4B00] focus:ring-[#8D4B00]"
              />
            </label>

            <label className="flex items-center justify-between text-xs cursor-pointer p-1.5 rounded-lg bg-stone-50 border border-stone-200">
              <span className="font-semibold text-stone-800">Denoise Background Audio</span>
              <input
                type="checkbox"
                checked={engines.removeNoise}
                onChange={(e) => updateEngineConfig('removeNoise', e.target.checked)}
                className="rounded text-[#8D4B00] focus:ring-[#8D4B00]"
              />
            </label>
          </div>
        </div>
      </section>

      {/* ASR Settings Modal */}
      {settingsModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs">
          <div className="w-full max-w-sm bg-white rounded-2xl p-5 shadow-2xl border border-stone-200 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 font-bold text-sm text-stone-900">
                <Key className="w-4 h-4 text-[#8D4B00]" />
                <span>Configure {selectedProvider.label} API Key</span>
              </div>
              <button
                onClick={() => setSettingsModalOpen(false)}
                className="w-6 h-6 rounded-full hover:bg-stone-100 flex items-center justify-center text-stone-400 hover:text-stone-700 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-stone-600">
              Enter your {selectedProvider.label} API key to enable speech recognition with this provider.
            </p>

            <div className="space-y-1">
              <input
                type="password"
                placeholder="Enter API Key…"
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                className="w-full text-xs p-2.5 rounded-lg bg-stone-50 border border-stone-200 focus:bg-white focus:outline-none focus:border-amber-400"
              />
              {keySavedMsg && (
                <div
                  className={`text-[10px] font-semibold mt-1 ${
                    keySavedMsg.startsWith('Error') ? 'text-rose-600' : 'text-emerald-700'
                  }`}
                >
                  {keySavedMsg}
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 mt-2">
              <button
                onClick={() => setSettingsModalOpen(false)}
                className="px-3 py-1.5 rounded-lg bg-stone-100 hover:bg-stone-200 text-xs font-semibold text-stone-700 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveApiKey}
                disabled={savingKey || !apiKeyInput.trim()}
                className="px-4 py-1.5 rounded-lg bg-[#8D4B00] hover:bg-[#743D00] text-xs font-bold text-white flex items-center gap-1.5 disabled:opacity-50 cursor-pointer shadow-xs"
              >
                {savingKey ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                <span>Save Key</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
