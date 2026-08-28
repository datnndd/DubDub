/**
 * Model Catalogue -> Engines (ASR tab) -> Deepgram Cloud ASR panel.
 *
 * Cloud-hosted fast transcription via Deepgram's Nova-2/Nova-3 API.
 * Configures the `deepgram-asr` backend model/api_key.
 *
 * Endpoints (loopback-only):
 *   GET  /api/settings/asr-deepgram        -> {model, has_key}
 *   PUT  /api/settings/asr-deepgram       body {model?, api_key?}
 *   POST /api/settings/asr-deepgram/test  -> {ok, status, latency_ms, …}
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Cloud, Plug } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { apiJson, apiFetch, apiPost } from '../../api/client';
import { SettingsSection, SettingRow, SettingsInput } from './primitives';
import { Button, Select } from '../../ui';

const DEEPGRAM_MODELS = [
  { value: 'nova-2', label: 'Nova-2 (Fast, Multilingual, Recommended)' },
  { value: 'nova-3', label: 'Nova-3 (Latest Flagship)' },
  { value: 'enhanced', label: 'Enhanced' },
  { value: 'base', label: 'Base' },
];

export default function AsrDeepgramPanel({ onSaved = null }) {
  const { t } = useTranslation();
  const [model, setModel] = useState('nova-2');
  const [apiKey, setApiKey] = useState('');
  const [hasKey, setHasKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [server, setServer] = useState({ model: 'nova-2' });

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const d = await apiJson('/api/settings/asr-deepgram');
      setModel(d?.model || 'nova-2');
      setHasKey(Boolean(d?.has_key));
      setApiKey('');
      setServer({ model: d?.model || 'nova-2' });
    } catch (e) {
      setError(e?.message || t('models.asrDeepgramLoadError'));
    }
  }, [t]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const edit = (setter) => (e) => {
    setter(e.target.value);
    setTestResult(null);
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch('/api/settings/asr-deepgram', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model,
          ...(apiKey ? { api_key: apiKey } : {}),
        }),
      });
      const d = await res.json();
      setModel(d.model || 'nova-2');
      setHasKey(Boolean(d.has_key));
      setApiKey('');
      setServer({ model: d.model || 'nova-2' });
      setSaved(true);
      onSaved?.();
      return true;
    } catch (e) {
      setError(e?.message || t('models.asrDeepgramSaveError'));
      return false;
    } finally {
      setSaving(false);
    }
  };

  const dirty = model !== server.model || apiKey !== '';

  const testConnection = async () => {
    setTesting(true);
    setTestResult(null);
    setError(null);
    try {
      if (dirty && !(await save())) return;
      const res = await apiPost('/api/settings/asr-deepgram/test');
      setTestResult(res);
    } catch (e) {
      setTestResult({ ok: false, status: 'request_failed', detail: e?.message });
    } finally {
      setTesting(false);
    }
  };

  const testMessage = (r) => {
    const ms = Math.round(r?.latency_ms || 0);
    switch (r?.status) {
      case 'ok':
        return t('models.asrDeepgramTestOk', { ms });
      case 'auth_failed':
        return t('models.asrDeepgramTestAuthFailed', { code: r.http_status });
      case 'http_error':
        return t('models.asrDeepgramTestHttpError', { code: r.http_status });
      case 'timeout':
        return t('models.asrDeepgramTestTimeout');
      case 'unreachable':
        return t('models.asrDeepgramTestUnreachable');
      case 'not_configured':
        return t('models.asrDeepgramTestNotConfigured');
      default:
        return r?.detail || t('odels.asrDeepgramTestFailed');
    }
  };

  return (
    <SettingsSection
      icon={Cloud}
      title={t('models.asrDeepgramTitle')}
      description={t('models.asrDeepgramDescription')}
    >
      {error && (
        <div className="perfpanel__error" role="alert">
          {error}
        </div>
      )}

      <SettingRow
        stack
        title={t('models.asrDeepgramModelTitle')}
        control={
          <Select
            value={model}
            onChange={edit(setModel)}
            data-testid="asr-deepgram-model"
          >
            {DEEPGRAM_MODELS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </Select>
        }
      />

      <SettingRow
        stack
        title={t('models.asrDeepgramApiKeyTitle')}
        hint={
          hasKey ? t('models.asrDeepgramKeyConfigured') : t('models.asrDeepgramApiKeyHint')
        }
        control={
          <>
            <SettingsInput
              mono
              type="password"
              value={apiKey}
              onChange={edit(setApiKey)}
              placeholder={hasKey ? '••••••• ' : t('odels.asrDeepgramApiKeyOptional')}
              data-testid="asr-deepgram-api-key"
            />
            <Button
              variant="subtle"
              size="sm"
              onClick={save}
              loading={saving}
              disabled={saving || testing || !dirty}
              data-testid="asr-deepgram-save"
            >
              {t('common.save')}
            </Button>
            {saved && !dirty && !saving && (
              <span
                className="text-[length:var(--text-xs)] text-[color:var(--chrome-fg-dim)]"
                role="status"
                data-testid="asr-deepgram-saved"
              >
                {t('models.asrDeepgramSaved')}
              </span>
            )}
          </>
        }
      />

      <SettingRow
        stack
        title={t('models.asrDeepgramTestTitle')}
        hint={t('models.asrDeepgramTestHint')}
        control={
          <>
            <Button
              variant="subtle"
              size="sm"
              onClick={testConnection}
              loading={testing}
              disabled={testing || saving || (!hasKey && !apiKey.trim())}
              leading={!testing && <Plug size={11} />}
              data-testid="asr-deepgram-test"
            >
              {testing ? t('models.asrDeepgramTesting') : t('models.asrDeepgramTest')}
            </Button>
            {testResult && !testing && (
              <span
                className={`text-[length:var(--text-xs)] ${
                  testResult.ok
                    ? 'text-[color:var(--chrome-severity-ok,#98971a)]'
                    : 'text-[color:var(--chrome-severity-err,#cc241d)]'
                }`}
                role="status"
                title={testResult.detail || undefined}
                data-testid="asr-deepgram-test-result"
              >
                {testMessage(testResult)}
              </span>
            )}
          </>
        }
      />
    </SettingsSection>
  );
}
