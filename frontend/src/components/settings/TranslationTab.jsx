/**
 * Settings → Translation (consolidated category).
 *
 * Pulls the translation controls into one home:
 *   • translateQuality pref (fast | autofit | cinematic) — zustand store binding.
 *   • A pointer to Settings → LLM Providers — the ONE place to configure the
 *     OpenAI-compatible LLM that powers Cinematic/Autofit translate, glossary
 *     extract, and dictation refinement. (Replaces the legacy inline LLM
 *     endpoint panel, whose TRANSLATE_* surface is fully covered by the
 *     registry's `custom` provider — a lone TRANSLATE_BASE_URL still resolves
 *     to `custom`, so nothing is lost.)
 *   • DeepL / Microsoft translator credentials — the non-LLM online translators.
 *     Same `/system/set-env` save path; these keys are in PERSISTENT_KEYS, so
 *     they survive restarts. HF_TOKEN stays in Credentials.
 */
import React from 'react';
import { Languages, Brain } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Segmented } from '../../ui';
import { useAppStore } from '../../store';
import { SettingsSection, SettingRow } from './primitives';
import { Button } from '../../ui';

// Non-LLM online-translator credentials (DeepL, Microsoft). The OpenAI-compatible
// LLM (TRANSLATE_*) is configured in Settings → LLM Providers, not here, so it
// isn't duplicated. HF_TOKEN lives in the Credentials category.
export default function TranslationTab() {
  const { t } = useTranslation();
  const translateQuality = useAppStore((s) => s.translateQuality);
  const setTranslateQuality = useAppStore((s) => s.setTranslateQuality);
  const openSettingsTab = useAppStore((s) => s.openSettingsTab);

  return (
    <>
      <SettingsSection
        icon={Languages}
        title={t('settings.translation', { defaultValue: 'Translation' })}
        description={t('settings.translation_desc', {
          defaultValue: 'How dubbing translates dialogue, and which engine does it.',
        })}
      >
        <SettingRow
          title={t('settings.translate_quality', { defaultValue: 'Translation quality' })}
          subtitle={t('settings.translate_quality_desc', {
            defaultValue: 'Fast is literal and quick; Cinematic uses the LLM for natural phrasing.',
          })}
          control={
            <Segmented
              size="sm"
              value={translateQuality}
              onChange={setTranslateQuality}
              items={[
                { value: 'fast', label: t('settings.translate_fast', { defaultValue: 'Fast' }) },
                {
                  value: 'autofit',
                  label: t('settings.translate_autofit', { defaultValue: 'Autofit' }),
                },
                {
                  value: 'cinematic',
                  label: t('settings.translate_cinematic', { defaultValue: 'Cinematic' }),
                },
              ]}
            />
          }
        />
      </SettingsSection>

      <SettingsSection
        icon={Brain}
        title={t('settings.translation_llm', { defaultValue: 'Translation LLM' })}
        description={t('settings.translation_llm_desc', {
          defaultValue: 'Cinematic and Autofit translation use a high-quality LLM.',
        })}
      >
        <SettingRow
          align="start"
          title={t('settings.translation_llm_row', { defaultValue: 'LLM provider' })}
          subtitle={t('settings.translation_llm_row_desc', {
            defaultValue:
              'Choose, test, and activate a provider (OpenAI, OpenRouter, Groq, a local Ollama, …) in LLM Providers. Keys are stored encrypted; local providers stay fully offline.',
          })}
          control={
            <Button
              variant="primary"
              size="sm"
              onClick={() => openSettingsTab('llm-providers')}
              data-testid="translation-open-llm-providers"
            >
              {t('settings.translation_open_llm', { defaultValue: 'Open LLM Providers' })}
            </Button>
          }
        />
      </SettingsSection>

    </>
  );
}
