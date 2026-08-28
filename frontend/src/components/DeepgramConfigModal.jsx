/**
 * DeepgramConfigModal — Accessible, dedicated popup dialog to configure
 * Deepgram API Key and Model with immediate "Test connection" and "Save & Activate".
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Cloud, Plug, CheckCircle2, AlertCircle, Key, Cpu, ShieldCheck } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { apiJson, apiFetch, apiPost } from '../api/client';
import { Dialog, Button, Select, Input } from '../ui';
import { useSelectEngine } from '../api/hooks';
import { toast } from 'react-hot-toast';

const DEEPGRAM_MODELS = [
  { value: 'nova-2', label: 'Nova-2 (Fast, Multilingual, Recommended)' },
  { value: 'nova-3', label: 'Nova-3 (Latest Flagship)' },
  { value: 'enhanced', label: 'Enhanced' },
  { value: 'base', label: 'Base' },
];

export default function DeepgramConfigModal({ open, onClose, onSaved }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const selectMutation = useSelectEngine();

  const [model, setModel] = useState('nova-2');
  const [apiKey, setApiKey] = useState('');
  const [hasKey, setHasKey] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [error, setError] = useState(null);

  const loadSettings = useCallback(async () => {
    setLoading(true);
    setError(null);
    setTestResult(null);
    try {
      const data = await apiJson('/api/settings/asr-deepgram');
      setModel(data?.model || 'nova-2');
      setHasKey(Boolean(data?.has_key));
      setApiKey('');
    } catch (e) {
      setError(e?.message || t('models.asrDeepgramLoadError'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    if (open) {
      loadSettings();
    }
  }, [open, loadSettings]);

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    setError(null);
    try {
      // If user typed a new key or model, save first so probe uses newest credentials
      if (apiKey.trim() || model) {
        await apiFetch('/api/settings/asr-deepgram', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model,
            ...(apiKey.trim() ? { api_key: apiKey.trim() } : {}),
          }),
        });
        setHasKey(true);
      }
      const res = await apiPost('/api/settings/asr-deepgram/test');
      setTestResult(res);
      if (res.ok) {
        toast.success(t('models.asrDeepgramTestOk', { ms: Math.round(res.latency_ms || 0) }));
      } else {
        toast.error(res.detail || t('models.asrDeepgramTestFailed'));
      }
    } catch (e) {
      setTestResult({ ok: false, status: 'request_failed', detail: e?.message });
      toast.error(e?.message || t('models.asrDeepgramTestFailed'));
    } finally {
      setTesting(false);
    }
  };

  const handleSaveAndActivate = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch('/api/settings/asr-deepgram', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model,
          ...(apiKey.trim() ? { api_key: apiKey.trim() } : {}),
        }),
      });
      const d = await res.json();
      setHasKey(Boolean(d.has_key));
      setApiKey('');

      // Invalidate engine cache so UI knows deepgram is available
      await queryClient.invalidateQueries({ queryKey: ['engines'] });

      // Automatically activate Deepgram as current ASR engine
      await selectMutation.mutateAsync({ family: 'asr', backendId: 'deepgram-asr' });

      toast.success(t('engines.deepgram_activated', { defaultValue: 'Deepgram Cloud ASR is now active!' }));
      onSaved?.();
      onClose?.();
    } catch (e) {
      setError(e?.message || t('models.asrDeepgramSaveError'));
      toast.error(e?.message || t('models.asrDeepgramSaveError'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={
        <div className="flex items-center gap-2 text-base font-semibold text-[color:var(--chrome-fg)]">
          <Cloud className="text-[color:var(--color-brand,#fabd2f)]" size={18} />
          {t('models.asrDeepgramTitle')}
        </div>
      }
      size="md"
    >
      <div className="flex flex-col gap-4 py-2">
        <p className="text-xs text-[color:var(--chrome-fg-dim,#a89984)] leading-relaxed">
          {t('models.asrDeepgramDescription')}
        </p>

        {error && (
          <div className="flex items-center gap-2 p-2.5 rounded-md bg-[rgba(204,36,29,0.15)] border border-[rgba(204,36,29,0.3)] text-xs text-[#fb4934]">
            <AlertCircle size={14} className="shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Model Selection */}
        <div className="flex flex-col gap-1.5">
          <label className="flex items-center gap-1.5 text-xs font-medium text-[color:var(--chrome-fg)]">
            <Cpu size={13} />
            {t('models.asrDeepgramModelTitle')}
          </label>
          <Select
            value={model}
            onChange={(e) => {
              setModel(e.target.value);
              setTestResult(null);
            }}
            disabled={loading || saving}
            data-testid="deepgram-modal-model"
          >
            {DEEPGRAM_MODELS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </Select>
        </div>

        {/* API Key */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <label className="flex items-center gap-1.5 text-xs font-medium text-[color:var(--chrome-fg)]">
              <Key size={13} />
              {t('models.asrDeepgramApiKeyTitle')}
            </label>
            <span className="text-[11px] text-[color:var(--chrome-fg-muted)]">
              {hasKey ? (
                <span className="inline-flex items-center gap-1 text-[#b8bb26]">
                  <CheckCircle2 size={11} /> {t('models.asrDeepgramKeyConfigured')}
                </span>
              ) : (
                <span className="text-[#fabd2f]">{t('engines.needs_key', { defaultValue: 'API Key Required' })}</span>
              )}
            </span>
          </div>
          <Input
            type="password"
            value={apiKey}
            onChange={(e) => {
              setApiKey(e.target.value);
              setTestResult(null);
            }}
            placeholder={hasKey ? '••••••••••••••••••••' : 'Paste Deepgram API Key (e.g. 5a1b...)'}
            disabled={loading || saving}
            autoComplete="off"
            data-testid="deepgram-modal-key"
          />
          <span className="text-[11px] text-[color:var(--chrome-fg-muted)]">
            {t('models.asrDeepgramApiKeyHint')}
          </span>
        </div>

        {/* Test Connection Result Box */}
        {testResult && (
          <div
            className={`flex items-center gap-2 p-2.5 rounded-md border text-xs ${
              testResult.ok
                ? 'bg-[rgba(184,187,38,0.12)] border-[rgba(184,187,38,0.3)] text-[#b8bb26]'
                : 'bg-[rgba(204,36,29,0.12)] border-[rgba(204,36,29,0.3)] text-[#fb4934]'
            }`}
          >
            {testResult.ok ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
            <span>
              {testResult.ok
                ? t('models.asrDeepgramTestOk', { ms: Math.round(testResult.latency_ms || 0) })
                : testResult.detail || t('models.asrDeepgramTestFailed')}
            </span>
          </div>
        )}

        {/* Actions Bar */}
        <div className="flex items-center justify-between gap-2 pt-2 border-t border-[color:var(--chrome-border,#3c3836)]">
          <Button
            variant="subtle"
            size="sm"
            onClick={handleTest}
            loading={testing}
            disabled={testing || saving || (!hasKey && !apiKey.trim())}
            leading={!testing && <Plug size={13} />}
            data-testid="deepgram-modal-test"
          >
            {testing ? t('models.asrDeepgramTesting') : t('models.asrDeepgramTest')}
          </Button>

          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={onClose} disabled={saving}>
              {t('common.cancel', { defaultValue: 'Cancel' })}
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleSaveAndActivate}
              loading={saving}
              disabled={saving || (!hasKey && !apiKey.trim())}
              leading={<ShieldCheck size={13} />}
              data-testid="deepgram-modal-save"
            >
              {t('engines.save_and_activate', { defaultValue: 'Save & Use Deepgram' })}
            </Button>
          </div>
        </div>
      </div>
    </Dialog>
  );
}
