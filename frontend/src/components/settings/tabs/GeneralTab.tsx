import React, { useState } from 'react';
import {
  Sliders,
  Globe,
  Film,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Check,
  Network,
} from 'lucide-react';
import { GeneralSettings, updateGeneralSettings } from '../../../api/settingsApi';
import { useDubDubStore } from '../../../store';

interface GeneralTabProps {
  general: GeneralSettings;
  onRefresh: () => Promise<void>;
}

export const GeneralTab: React.FC<GeneralTabProps> = ({ general, onRefresh }) => {
  const [form, setForm] = useState<GeneralSettings>(general);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  React.useEffect(() => {
    setForm(general);
  }, [general]);

  const languages = useDubDubStore((s) => s.backend.options.languages || []);

  const handleSave = async () => {
    setSaving(true);
    setFeedback(null);
    try {
      await updateGeneralSettings(form);
      await onRefresh();
      const store = useDubDubStore.getState();
      if (store.currentStep === 1 && !store.selectedFile) {
        if (form.defaultSourceLanguage) {
          const opt = store.backend.options.languages?.find((l: any) => l.code === form.defaultSourceLanguage);
          store.updateSourceLanguage(form.defaultSourceLanguage, opt?.name || form.defaultSourceLanguage);
        }
        if (form.defaultTargetLanguage) {
          const opt = store.backend.options.languages?.find((l: any) => l.code === form.defaultTargetLanguage);
          store.updateTargetLanguage(form.defaultTargetLanguage, opt?.name || form.defaultTargetLanguage);
        }
      }
      setFeedback({ type: 'success', message: 'General settings updated successfully' });
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message || 'Failed to update general settings' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Network Proxy Section */}
      <div className="bg-white rounded-xl border border-stone-200 p-4 shadow-2xs space-y-3">
        <div className="flex items-center gap-2 border-b border-stone-100 pb-2">
          <Network className="w-4 h-4 text-[#8D4B00]" />
          <h4 className="font-bold text-xs text-stone-900">Network &amp; Proxy</h4>
        </div>

        <div>
          <label className="text-[10px] font-semibold text-stone-600 block mb-1">
            HTTP / HTTPS / SOCKS5 Proxy URL
          </label>
          <input
            type="text"
            placeholder="e.g. http://127.0.0.1:7890 or socks5://127.0.0.1:1080"
            value={form.proxy}
            onChange={(e) => setForm((prev) => ({ ...prev, proxy: e.target.value }))}
            className="w-full text-xs p-2 bg-stone-50 rounded-lg border border-stone-200 focus:bg-white focus:outline-none focus:border-amber-400 font-mono"
          />
          <p className="text-[10px] text-stone-400 mt-1">
            Used for outbound external API calls (Deepgram, OpenAI, ElevenLabs, Gemini). Leave empty for direct network.
          </p>
        </div>
      </div>

      {/* Default Languages Section */}
      <div className="bg-white rounded-xl border border-stone-200 p-4 shadow-2xs space-y-3">
        <div className="flex items-center gap-2 border-b border-stone-100 pb-2">
          <Globe className="w-4 h-4 text-[#8D4B00]" />
          <h4 className="font-bold text-xs text-stone-900">Default Workflow Languages</h4>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="text-[10px] font-semibold text-stone-600 block mb-1">Default Source Language</label>
            <select
              value={form.defaultSourceLanguage}
              onChange={(e) => setForm((prev) => ({ ...prev, defaultSourceLanguage: e.target.value }))}
              className="w-full text-xs p-2 bg-stone-50 rounded-lg border border-stone-200 focus:bg-white focus:outline-none focus:border-amber-400"
            >
              {languages.map((l: any) => (
                <option key={l.code} value={l.code}>
                  {l.name} ({l.code})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-[10px] font-semibold text-stone-600 block mb-1">Default Target Language</label>
            <select
              value={form.defaultTargetLanguage}
              onChange={(e) => setForm((prev) => ({ ...prev, defaultTargetLanguage: e.target.value }))}
              className="w-full text-xs p-2 bg-stone-50 rounded-lg border border-stone-200 focus:bg-white focus:outline-none focus:border-amber-400"
            >
              {languages.map((l: any) => (
                <option key={l.code} value={l.code}>
                  {l.name} ({l.code})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Video Rendering Defaults */}
      <div className="bg-white rounded-xl border border-stone-200 p-4 shadow-2xs space-y-3">
        <div className="flex items-center gap-2 border-b border-stone-100 pb-2">
          <Film className="w-4 h-4 text-[#8D4B00]" />
          <h4 className="font-bold text-xs text-stone-900">Video Export Quality Defaults</h4>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-[10px] font-semibold text-stone-600">CRF Value (Quality)</label>
              <span className="font-mono text-xs font-bold text-[#8D4B00]">{form.crf}</span>
            </div>
            <input
              type="range"
              min="18"
              max="32"
              step="1"
              value={form.crf}
              onChange={(e) => setForm((prev) => ({ ...prev, crf: parseInt(e.target.value, 10) }))}
              className="w-full accent-[#8D4B00] cursor-pointer"
            />
            <div className="flex justify-between text-[9px] text-stone-400">
              <span>18 (Highest Quality)</span>
              <span>23 (Balanced)</span>
              <span>32 (Smallest Size)</span>
            </div>
          </div>

          <div>
            <label className="text-[10px] font-semibold text-stone-600 block mb-1">FFmpeg Encoding Preset</label>
            <select
              value={form.preset}
              onChange={(e) => setForm((prev) => ({ ...prev, preset: e.target.value }))}
              className="w-full text-xs p-2 bg-stone-50 rounded-lg border border-stone-200 focus:bg-white focus:outline-none focus:border-amber-400"
            >
              <option value="ultrafast">Ultrafast (Draft)</option>
              <option value="superfast">Superfast</option>
              <option value="veryfast">Veryfast</option>
              <option value="faster">Faster</option>
              <option value="fast">Fast</option>
              <option value="medium">Medium</option>
              <option value="slow">Slow (Recommended)</option>
              <option value="slower">Slower</option>
            </select>
          </div>
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

      {/* Save Button */}
      <div className="flex justify-end pt-2">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-1.5 rounded-lg bg-[#8D4B00] hover:bg-[#743D00] text-white text-xs font-bold flex items-center gap-1.5 disabled:opacity-50 cursor-pointer shadow-2xs transition-colors"
        >
          {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
          <span>Save General Settings</span>
        </button>
      </div>
    </div>
  );
};
