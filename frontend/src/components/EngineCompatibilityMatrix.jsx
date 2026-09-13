import React from 'react';
import { useTranslation } from 'react-i18next';
import { Badge, Button, Tabs } from '../ui';

const FAMILIES = ['tts', 'asr', 'llm'];

/** Minimal provider picker for the web-only runtime boundary. */
export default function EngineCompatibilityMatrix({
  family = 'tts',
  sharedEngines,
  onSelect,
  onFamilyChange,
}) {
  const { t } = useTranslation();
  const payload = sharedEngines?.data?.[family] || {};
  const rows = payload.backends || [];
  const items = FAMILIES.map((id) => ({
    id,
    label: id === 'tts' ? 'TTS' : id === 'asr' ? 'ASR' : 'LLM',
  }));

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3" data-testid="engine-provider-picker">
      <Tabs items={items} value={family} onChange={onFamilyChange} size="sm" />
      {sharedEngines?.isLoading ? <p>{t('common.loading')}</p> : null}
      {sharedEngines?.error ? <p role="alert">{sharedEngines.error.message}</p> : null}
      <div className="grid gap-2">
        {rows.map((engine) => {
          const active = payload.active === engine.id;
          const available = engine.available !== false;
          return (
            <div
              key={engine.id}
              className="flex items-center gap-3 rounded-lg border border-transparent p-3"
              data-testid={`engine-${engine.id}`}
            >
              <div className="min-w-0 flex-1">
                <div className="font-medium">{engine.display_name || engine.id}</div>
                {!available && engine.reason ? (
                  <div className="text-xs text-[var(--chrome-fg-muted)]">{engine.reason}</div>
                ) : null}
              </div>
              <Badge tone={active ? 'success' : available ? 'neutral' : 'warn'}>
                {active ? t('engines.active') : available ? t('engines.available') : t('engines.unavailable')}
              </Badge>
              {!active && available ? (
                <Button size="sm" onClick={() => onSelect?.(family, engine.id)}>
                  {t('engines.use')}
                </Button>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
