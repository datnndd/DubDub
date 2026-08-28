/**
 * AsrEngineSelector — Clean, prominent ASR Engine selector with inline
 * API settings button for cloud engines (Deepgram, OpenAI-compat).
 */
import React, { useState } from 'react';
import { Settings } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useEngines, useSelectEngine } from '../api/hooks';
import { Button } from '../ui';
import DeepgramConfigModal from './DeepgramConfigModal';
import { notifyEngineSelected } from '../utils/engineSelectToast';
import { toast } from 'react-hot-toast';

export default function AsrEngineSelector({ className = '' }) {
  const { t } = useTranslation();
  const { data: engines, isLoading } = useEngines();
  const selectMutation = useSelectEngine();
  const [deepgramModalOpen, setDeepgramModalOpen] = useState(false);

  const asrData = engines?.asr;
  const backends = asrData?.backends || [];
  const activeId = asrData?.active || 'faster-whisper';

  const isDeepgramActive = activeId === 'deepgram-asr';
  const deepgramBackend = backends.find((b) => b.id === 'deepgram-asr');
  const isDeepgramReady = deepgramBackend?.available ?? false;

  const handleSelect = async (backendId) => {
    if (backendId === activeId) return;

    if (backendId === 'deepgram-asr') {
      if (!isDeepgramReady) {
        // If Deepgram lacks API key, pop up the settings modal immediately
        setDeepgramModalOpen(true);
        return;
      }
    }

    try {
      const res = await selectMutation.mutateAsync({ family: 'asr', backendId });
      notifyEngineSelected(res, t, 'asr');
    } catch (e) {
      toast.error(e?.message || t('engines.switch_failed'));
    }
  };

  return (
    <div className={`inline-flex items-center gap-2 ${className}`}>
      <label className="inline-flex items-center gap-1.5 text-xs text-[var(--muted,#a89984)] whitespace-nowrap">
        <span className="font-medium text-[color:var(--chrome-fg,#ebdbb2)]">
          {t('engines.asr_label', { defaultValue: 'ASR Engine:' })}
        </span>
        <select
          className="px-2 py-1 text-xs rounded-md border border-[var(--border,#3c3836)] bg-[var(--input-bg,#282828)] text-[color:var(--chrome-fg,#ebdbb2)] font-medium cursor-pointer transition-colors focus:border-[var(--color-brand,#fabd2f)] focus:outline-none"
          value={activeId}
          onChange={(e) => handleSelect(e.target.value)}
          disabled={isLoading || selectMutation.isPending}
          data-testid="asr-engine-select"
        >
          {/* Main options grouped or listed cleanly */}
          {backends.length > 0 ? (
            backends.map((b) => (
              <option key={b.id} value={b.id}>
                {b.display_name} {b.available ? '' : `(${t('engines.needs_setup', { defaultValue: 'Setup needed' })})`}
              </option>
            ))
          ) : (
            <>
              <option value="faster-whisper">Faster-Whisper (Local)</option>
              <option value="deepgram-asr">Deepgram (Cloud API)</option>
            </>
          )}
        </select>
      </label>

      {/* Prominent inline API Settings button for Deepgram */}
      {isDeepgramActive && (
        <Button
          variant={isDeepgramReady ? "subtle" : "primary"}
          size="xs"
          onClick={() => setDeepgramModalOpen(true)}
          className="!h-[24px] !px-2 !py-0 text-[11px] gap-1 shrink-0"
          title={isDeepgramReady ? t('models.asrDeepgramKeyConfigured') : t('models.asrDeepgramApiKeyHint')}
          data-testid="open-deepgram-modal"
        >
          <Settings size={12} className={isDeepgramReady ? "text-[#b8bb26]" : "animate-pulse"} />
          <span>{t('engines.deepgram_settings_btn', { defaultValue: 'Deepgram API' })}</span>
          {isDeepgramReady ? (
            <span className="w-1.5 h-1.5 rounded-full bg-[#b8bb26] inline-block" />
          ) : (
            <span className="text-[10px] px-1 py-0.2 rounded bg-[rgba(250,189,47,0.2)] text-[#fabd2f]">
              {t('engines.setup_key', { defaultValue: 'Config Key' })}
            </span>
          )}
        </Button>
      )}

      {/* Modal Dialog */}
      <DeepgramConfigModal
        open={deepgramModalOpen}
        onClose={() => setDeepgramModalOpen(false)}
      />
    </div>
  );
}
