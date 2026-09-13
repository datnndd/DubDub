import { useEffect, useState } from 'react';
import {
  Sparkles,
  Loader,
  ChevronDown,
  ChevronUp,
  Globe,
  UserSquare2,
  Languages,
  Wand2,
} from 'lucide-react';
import { Button, Segmented, Progress } from '../../ui';
import { useAppStore } from '../../store';
import WaveformTimeline from '../WaveformTimeline';
import MultiLangPicker from '../MultiLangPicker';
import { API } from '../../api/client';
import { dubListTracks } from '../../api/dub';
import { LANG_CODES } from '../../utils/languages';
import ALL_LANGUAGES from '../../languages.json';
import { POPULAR_LANGS, PRESETS } from '../../utils/constants';
import { dialectOptionsFor, dialectLabel, dialectMatchesLang } from '../../api/dialects';
import { dubSegmentsText } from '../../api/dub';
import { autoProfileId } from '../../utils/segments';

// ── Translation-settings bar utility class clusters ──────────────────────
const SETTINGS_SUMMARY =
  'flex items-center gap-[var(--space-2)] px-[var(--space-3)] py-[3px] mb-[3px] bg-[var(--chrome-bg)] border border-transparent rounded-[var(--chrome-radius-pill)] font-[family-name:var(--font-sans)] text-[0.66rem] text-[var(--chrome-fg-muted)]';
const SUMMARY_TRIGGER =
  'inline-flex items-center gap-[5px] flex-1 min-w-0 bg-transparent border-none text-fg-muted cursor-pointer py-[2px] px-0 [font:inherit] text-left';
const SETTINGS_BAR =
  'flex flex-col gap-[3px] max-[900px]:gap-[6px] mb-[4px] px-[8px] py-[4px] bg-[var(--chrome-bg)] border border-transparent rounded-[var(--chrome-radius-pill)]';
const FIELD = 'flex flex-col gap-[1px] min-w-0';
const FIELD_RESP = 'max-[960px]:basis-full max-[960px]:min-w-0';
const FIELD_LABEL =
  'label-row !text-[0.58rem] !text-fg-muted !m-0 whitespace-nowrap overflow-hidden text-ellipsis';
const FIELD_INPUT = 'input-base !w-full !text-[0.65rem] !px-[5px] !py-[3px]';

// Single source of truth for the translate / clean-up action pair — it used
// to be duplicated in the collapsed summary and the expanded settings bar and
// had drifted (different labels + variants for the same actions).
function SettingsActions({
  t,
  onTranslate,
  onCleanup,
  onOpenHardsubDialog,
  hardsubRunning,
  canHardsub,
  translating,
  canTranslate,
  canCleanup,
  hasAny,
  translateVariant = 'subtle',
  cleanupFirst = false,
}) {
  const translateBtn = (
    <Button
      variant={translateVariant}
      size="sm"
      onClick={onTranslate}
      disabled={canTranslate}
      loading={translating}
      leading={!translating && <Languages size={10} />}
    >
      {translating ? t('dub.translating') : hasAny ? t('dub.retranslate') : t('dub.translate_all')}
    </Button>
  );
  const cleanupBtn = (
    <Button
      variant="subtle"
      size="sm"
      onClick={onCleanup}
      disabled={canCleanup}
      title={t('dub.clean_up_title')}
      leading={<Wand2 size={10} />}
    >
      {t('dub.clean_up')}
    </Button>
  );
  const hardsubBtn = onOpenHardsubDialog ? (
    <Button
      variant="subtle"
      size="sm"
      onClick={onOpenHardsubDialog}
      disabled={hardsubRunning || !canHardsub}
      loading={hardsubRunning}
      leading={!hardsubRunning && <Languages size={10} />}
      title={t('dub.hardsub_title')}
    >
      {t('dub.hardsub_btn')}
    </Button>
  ) : null;
  if (cleanupFirst) {
    return (
      <>
        {cleanupBtn}
        {translateBtn}
        {hardsubBtn}
      </>
    );
  }
  return (
    <>
      {translateBtn}
      {cleanupBtn}
      {hardsubBtn}
    </>
  );
}

export default function DubLeftColumn({
  hasDubbedTrack,
  t,
  previewMode,
  setPreviewMode,
  dubTracks,
  videoSrc,
  waveformRef,
  dubJobId,
  dubSegments,
  timelineOnsets,
  timelineSelSegId,
  setTimelineSelSegId,
  incrementalPlan,
  segmentMoveResize,
  segmentDelete,
  onTimelinePreviewSegment,
  dubStep,
  dubProgress,
  fmtDur,
  genElapsed,
  genRemaining,
  speakerClones,
  setDubSegments,
  profiles,
  settingsOpen,
  setSettingsOpen,
  dubLang,
  dubLangCode,
  translateQuality,
  translateProvider,
  dubInstruct,
  setDubInstruct,
  handleTranslateAll,
  isTranslating,
  hasAnyTranslation,
  handleCleanupSegments,
  onOpenHardsubDialog,
  hardsubRunning,
  setDubLang,
  setDubLangCode,
  dubDialect,
  setDubDialect,
  i18n,
  setTranslateProvider,
  setTranslateQuality,
  multiLangMode,
  setMultiLangMode,
  multiLangs,
  setMultiLangs,
  multiLangProgress,
  editSegments,
}) {
  // Two-stage LLM translation quality — only meaningful (and only rendered)
  // when the LLM engine is the active translator. Persisted prefs.
  const autoGlossary = useAppStore((s) => s.autoGlossary);
  const setAutoGlossary = useAppStore((s) => s.setAutoGlossary);
  const reflectPass = useAppStore((s) => s.reflectPass);
  const setReflectPass = useAppStore((s) => s.setReflectPass);
  // Opt-in LLM condensation suggestions for segments the duration planner
  // classifies as impossible to fit (default OFF — needs an LLM).
  const condenseSuggest = useAppStore((s) => s.condenseSuggest);
  const setCondenseSuggest = useAppStore((s) => s.setCondenseSuggest);
  // Per-track metadata (duration + timing strategy) for the pill tooltips.
  // The store only carries the track codes, so hydrate lazily from the
  // existing GET /dub/tracks/{job_id} once the editor shows tracks (re-runs
  // when a new language finishes and dubTracks changes). Failure-silent:
  // the pills render fine without tooltips.
  const [trackInfo, setTrackInfo] = useState({});
  useEffect(() => {
    if (!hasDubbedTrack || !dubJobId) return undefined;
    let cancelled = false;
    dubListTracks(dubJobId)
      .then((tracks) => {
        if (!cancelled) setTrackInfo(tracks || {});
      })
      .catch(() => {
        /* tooltip enrichment only — never block or toast */
      });
    return () => {
      cancelled = true;
    };
  }, [hasDubbedTrack, dubJobId, dubTracks]);
  const trackTooltip = (code) => {
    const info = trackInfo[code];
    if (!info) return undefined;
    const parts = [];
    if (Number.isFinite(info.duration) && info.duration > 0) {
      parts.push(
        t('dub.track_tip_duration', {
          duration: fmtDur(Math.round(info.duration)),
          defaultValue: 'Duration {{duration}}',
        }),
      );
    }
    if (info.timing_strategy) {
      // Reuse the timing-strategy display names where they exist
      // (dub.timing_<id>); unknown/future strategies fall back to the raw id.
      const strategy = t(`dub.timing_${info.timing_strategy}`, {
        defaultValue: info.timing_strategy,
      });
      parts.push(t('dub.track_tip_timing', { strategy, defaultValue: 'Timing {{strategy}}' }));
    }
    return parts.length ? parts.join(' · ') : undefined;
  };

  async function hydrateMissingTranslations(code) {
    const st = useAppStore.getState();
    const jobId = st.dubJobId;
    if (!jobId) return;
    const missing = st.dubSegments.some(
      (seg) =>
        !(
          seg.translations &&
          typeof seg.translations[code] === 'string' &&
          seg.translations[code].trim()
        ),
    );
    if (!missing) return;
    try {
      const texts = await dubSegmentsText(jobId, code);
      if (!texts || !Object.keys(texts).length) return;
      const cur = useAppStore.getState();
      if (cur.dubLangCode !== code) return; // user already switched again
      cur.setDubSegments(
        cur.dubSegments.map((seg, i) => {
          const key = seg.id != null ? String(seg.id) : String(i);
          const incoming = texts[key];
          const has =
            seg.translations &&
            typeof seg.translations[code] === 'string' &&
            seg.translations[code].trim();
          if (has || typeof incoming !== 'string' || !incoming.trim()) return seg;
          return {
            ...seg,
            text: incoming,
            translations: { ...seg.translations, [code]: incoming },
          };
        }),
      );
    } catch {
      /* advisory — rows keep their previous-language text, as before */
    }
  }

  return (
    <div className="studio-panel dub-panel-col">
      {/* Hardsub OCR — vẽ vùng phụ đề trên video rồi quét */}
      {hasDubbedTrack && (
        <div
          className="dub-lang-switch"
          role="radiogroup"
          aria-label={t('dub.preview_language', { defaultValue: 'Preview language' })}
        >
          <button
            type="button"
            role="radio"
            aria-checked={previewMode === 'original'}
            className={`dub-lang-pill ${previewMode === 'original' ? 'is-active' : ''}`}
            onClick={() => setPreviewMode('original')}
          >
            {t('dub.original_audio')}
          </button>
          {dubTracks.map((code) => {
            const label = LANG_CODES.find((lc) => lc.code === code)?.label || code.toUpperCase();
            return (
              <button
                key={code}
                type="button"
                role="radio"
                aria-checked={previewMode === code}
                className={`dub-lang-pill ${previewMode === code ? 'is-active' : ''}`}
                onClick={() => {
                  setPreviewMode(code);
                  // The transcript/segment list follows the previewed track:
                  // swap segment texts to this language's saved translations
                  // (the P1.2 per-language store — non-destructive, exactly
                  // what the language dropdown and multi-language generate
                  // already do). Without this, previewing German played
                  // German audio over, say, Bengali segment text.
                  const st = useAppStore.getState();
                  st.setDubLang(label);
                  st.switchDubLangCode(code);
                  // Review finding (#1148): the in-browser translations map
                  // can be PARTIAL (tracks generated before per-language
                  // persistence, partial regens) — the non-destructive switch
                  // then leaves those rows in the previous language, a
                  // mixed-language transcript under a single-language track.
                  // Hydrate the gaps from the backend's authoritative
                  // segments_i18n store. Failure-silent: no data → the rows
                  // keep what they had, exactly the pre-hydration behavior.
                  hydrateMissingTranslations(code);
                }}
                title={trackTooltip(code)}
              >
                {label}
              </button>
            );
          })}
        </div>
      )}
      <WaveformTimeline
        key={videoSrc}
        ref={waveformRef}
        audioSrc={`${API}/dub/audio/${dubJobId}`}
        videoSrc={videoSrc}
        segments={dubSegments}
        onsets={timelineOnsets}
        selectedSegId={timelineSelSegId}
        onSelectSeg={setTimelineSelSegId}
        incrementalPlan={incrementalPlan}
        onSegmentCommit={segmentMoveResize}
        onSegmentDelete={segmentDelete}
        onPreviewSegment={onTimelinePreviewSegment}
        disabled={dubStep === 'generating' || dubStep === 'stopping'}
        overlayContent={
          dubStep === 'generating' || dubStep === 'stopping' ? (
            <div className="flex flex-col items-center gap-[6px] w-full p-[10px] backdrop-blur-[2px]">
              <div className="flex items-center gap-[6px]">
                {dubStep === 'stopping' ? (
                  <Loader className="spinner" size={14} color="#a89984" />
                ) : (
                  <Sparkles className="spinner" size={14} color="#d3869b" />
                )}
                <span
                  className={`font-semibold text-[0.75rem] [font-variant-numeric:tabular-nums] tracking-[0.01em] ${dubStep === 'stopping' ? 'text-fg-muted' : 'text-fg'}`}
                >
                  {dubStep === 'stopping'
                    ? t('dub.stopping')
                    : t('dub.generate_dub') + ` ${dubProgress.current}/${dubProgress.total}…`}
                </span>
              </div>
              {dubStep === 'generating' && (
                <>
                  <div className="flex gap-[var(--space-4)] text-[0.65rem] text-fg-muted [font-variant-numeric:tabular-nums]">
                    <span>
                      ⏱ {fmtDur(genElapsed)} {t('dub.elapsed')}
                    </span>
                    {genRemaining !== null && (
                      <span>
                        ~{fmtDur(genRemaining)} {t('dub.remaining')}
                      </span>
                    )}
                  </div>
                  <div className="w-[80%] max-w-[240px] my-[1px]">
                    <Progress
                      value={
                        dubProgress.total ? (dubProgress.current / dubProgress.total) * 100 : 0
                      }
                      tone="brand"
                      size="sm"
                    />
                  </div>
                  {dubProgress.text && (
                    <span className="text-[0.62rem] text-fg-muted">{dubProgress.text}</span>
                  )}
                </>
              )}
            </div>
          ) : null
        }
      />

      {/* Cast — per-speaker voice assignment. When the auto-clone
                  extractor found a usable passage per speaker (≥5s from the
                  isolated vocals), that option becomes first-class in the
                  dropdown. It's also pre-selected on the segments so "new
                  language = same speaker's voice" works by default. */}
      {dubSegments.some((s) => s.speaker_id) && (
        <div className="mt-[2px] px-[var(--space-3)] py-[3px] bg-[var(--chrome-bg)] rounded-[var(--chrome-radius-pill)] border border-transparent">
          <div className="flex gap-[var(--space-2)] items-center flex-wrap">
            <span
              className="font-[family-name:var(--chrome-font-mono)] text-[length:var(--chrome-label-size)] text-[var(--chrome-fg-muted)] tracking-[var(--chrome-label-track)] uppercase font-semibold"
              title={t('dub.cast_title')}
            >
              {t('dub.cast')}
            </span>
            {[...new Set(dubSegments.map((s) => s.speaker_id).filter(Boolean))].map((spk) => {
              const autoId = autoProfileId(spk);
              const clone = speakerClones[spk];
              return (
                <div key={spk} className="dub-cast__pair">
                  <span className="font-[family-name:var(--chrome-font-mono)] text-[0.62rem] text-[var(--chrome-fg)]">
                    {spk}:
                  </span>
                  <select
                    className="input-base dub-cast__select"
                    value={dubSegments.find((s) => s.speaker_id === spk)?.profile_id || ''}
                    onChange={(e) => {
                      const val = e.target.value;
                      setDubSegments(
                        dubSegments.map((s) =>
                          s.speaker_id === spk ? { ...s, profile_id: val } : s,
                        ),
                      );
                    }}
                  >
                    {clone && (
                      <option value={autoId}>
                        {t('dub.from_video', { duration: clone.duration.toFixed(1) })}
                      </option>
                    )}
                    <option value="">{t('dub.default')}</option>
                    {profiles.length > 0 && (
                      <optgroup label={t('dub.clone_profiles')}>
                        {profiles.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.name}
                          </option>
                        ))}
                      </optgroup>
                    )}
                    {PRESETS.length > 0 && (
                      <optgroup label={t('dub.design_presets')}>
                        {PRESETS.map((p) => (
                          <option key={p.id} value={`preset:${p.id}`}>
                            {p.name}
                          </option>
                        ))}
                      </optgroup>
                    )}
                  </select>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Translation settings — collapsed or expanded */}
      {!settingsOpen && (
        <div className={SETTINGS_SUMMARY}>
          <button
            type="button"
            className={SUMMARY_TRIGGER}
            onClick={() => setSettingsOpen(true)}
            title={t('dub.edit_settings')}
          >
            <ChevronDown size={10} />
            <span>
              <strong className="text-[var(--chrome-fg)] font-semibold">{dubLang}</strong> ·{' '}
              {dubLangCode} · {translateQuality} ·{' '}
              <span style={{ color: '#b8bb26' }}>●</span>{' '}
              {translateProvider}
            </span>
            {dubInstruct && (
              <span className="text-[var(--chrome-fg-dim)] italic ml-[var(--space-2)]">
                {t('dub.style_label_prefix')}
                {dubInstruct}
              </span>
            )}
          </button>
          <SettingsActions
            t={t}
            onOpenHardsubDialog={onOpenHardsubDialog}
            hardsubRunning={hardsubRunning}
            canHardsub={!!dubJobId}
            onTranslate={handleTranslateAll}
            onCleanup={handleCleanupSegments}
            translating={isTranslating}
            canTranslate={isTranslating || !dubSegments.length}
            canCleanup={!dubSegments.length || !dubJobId}
            hasAny={hasAnyTranslation}
          />
        </div>
      )}
      {settingsOpen && (
        <div className={SETTINGS_BAR}>
          <div className="flex flex-wrap gap-x-[6px] gap-y-[4px] items-end">
            <button
              type="button"
              className={`${SUMMARY_TRIGGER} flex-[0_0_auto] !px-[4px] self-center`}
              onClick={() => setSettingsOpen(false)}
              title={t('dub.collapse_settings')}
            >
              <ChevronUp size={10} />
            </button>
            <div className={`${FIELD} flex-[1_1_100px] min-w-[70px] ${FIELD_RESP}`}>
              <div className={FIELD_LABEL}>
                <Globe className="label-icon" size={9} /> {t('dub.language')}
              </div>
              <select
                className={FIELD_INPUT}
                value={dubLang}
                onChange={(e) => {
                  const lang = e.target.value;
                  setDubLang(lang);
                  const match = LANG_CODES.find(
                    (lc) => lc.label.toLowerCase() === lang.toLowerCase(),
                  );
                  if (match) {
                    setDubLangCode(match.code);
                    // #280: a dialect belongs to one language — clear it
                    // whenever the new target doesn't match.
                    if (!dialectMatchesLang(dubDialect, match.code)) setDubDialect('');
                  }
                }}
              >
                <optgroup label={t('dub.popular')}>
                  {POPULAR_LANGS.map((l) => (
                    <option key={`p-${l}`} value={l}>
                      {l}
                    </option>
                  ))}
                </optgroup>
                <optgroup label={t('dub.all_languages')}>
                  {ALL_LANGUAGES.filter((l) => !POPULAR_LANGS.includes(l)).map((l) => (
                    <option key={l} value={l}>
                      {l}
                    </option>
                  ))}
                </optgroup>
              </select>
            </div>
            <div className={`${FIELD} flex-[0_1_72px] min-w-[52px] ${FIELD_RESP}`}>
              <div className={FIELD_LABEL}>{t('dub.iso_code')}</div>
              <select
                className={FIELD_INPUT}
                value={dubLangCode}
                onChange={(e) => {
                  const code = e.target.value;
                  setDubLangCode(code);
                  if (!dialectMatchesLang(dubDialect, code)) setDubDialect('');
                }}
              >
                {LANG_CODES.map((lc) => (
                  <option key={lc.code} value={lc.code}>
                    {lc.code} — {lc.label}
                  </option>
                ))}
              </select>
            </div>
            {/* #280: regional dialect / vocabulary. Only rendered for
                      languages with curated variants; region names come from
                      Intl.DisplayNames so they localize with the UI for free. */}
            {dialectOptionsFor(dubLangCode).length > 0 && (
              <div className={`${FIELD} flex-[0_1_110px] min-w-[80px] ${FIELD_RESP}`}>
                <div className={FIELD_LABEL} title={t('dub.dialect_title')}>
                  {t('dub.dialect_label')}
                </div>
                <select
                  className={FIELD_INPUT}
                  value={dialectMatchesLang(dubDialect, dubLangCode) ? dubDialect : ''}
                  onChange={(e) => setDubDialect(e.target.value)}
                >
                  <option value="">{t('dub.dialect_default')}</option>
                  {dialectOptionsFor(dubLangCode).map((d) => (
                    <option key={d} value={d}>
                      {dialectLabel(d, i18n.language)}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div className={`${FIELD} flex-[1.4_1_130px] min-w-[90px] ${FIELD_RESP}`}>
              <div className={`${FIELD_LABEL} !overflow-visible flex items-center`}>
                {t('dub.engine_label')}
              </div>
              <select
                className={FIELD_INPUT}
                value={translateProvider}
                onChange={(e) => setTranslateProvider(e.target.value)}
              >
                <option value="google">Google Translate</option>
                <option value="openai">LLM (OpenAI-compatible)</option>
              </select>
            </div>
            <div className={`${FIELD} flex-[0_1_auto] min-w-[80px] ${FIELD_RESP}`}>
              <div className={FIELD_LABEL} title={t('dub.quality_title')}>
                {t('dub.quality_label')}
              </div>
              <Segmented
                className="w-full"
                size="sm"
                value={translateQuality}
                onChange={setTranslateQuality}
                items={[
                  { value: 'fast', label: t('dub.fast_quality') },
                  {
                    value: 'autofit',
                    label: t('dub.autofit_quality', { defaultValue: 'Autofit' }),
                  },
                  { value: 'cinematic', label: t('dub.cinematic_quality') },
                ]}
              />
              {/* Opt-in (default OFF): when the duration planner marks a
                  translated line "impossible" for its slot, ask the LLM for a
                  shorter rewrite the user can apply per segment. */}
              <label
                className="flex items-center gap-[4px] mt-[3px] text-[0.55rem] text-fg-muted cursor-pointer select-none"
                title={t('dub.condense_title')}
              >
                <input
                  type="checkbox"
                  checked={condenseSuggest}
                  onChange={(e) => setCondenseSuggest(e.target.checked)}
                  className="cursor-pointer"
                />
                {t('dub.condense_label')}
              </label>
            </div>
            {/* LLM engine only: auto-glossary + reflect pass. Both default ON;
                the reflect tooltip is explicit that it multiplies LLM calls. */}
            {translateProvider === 'openai' && (
              <div
                className={`${FIELD} flex-[0_0_auto] ${FIELD_RESP} justify-end gap-[2px] pb-[2px]`}
              >
                <label
                  className="flex items-center gap-[4px] text-[0.6rem] text-[var(--chrome-fg-muted)] cursor-pointer whitespace-nowrap"
                  title={t('dub.auto_glossary_title')}
                >
                  <input
                    type="checkbox"
                    className="accent-[var(--color-brand)] cursor-pointer"
                    checked={autoGlossary}
                    onChange={(e) => setAutoGlossary(e.target.checked)}
                  />
                  <span>{t('dub.auto_glossary_label')}</span>
                </label>
                <label
                  className="flex items-center gap-[4px] text-[0.6rem] text-[var(--chrome-fg-muted)] cursor-pointer whitespace-nowrap"
                  title={t('dub.reflect_title')}
                >
                  <input
                    type="checkbox"
                    className="accent-[var(--color-brand)] cursor-pointer"
                    checked={reflectPass}
                    onChange={(e) => setReflectPass(e.target.checked)}
                  />
                  <span>{t('dub.reflect_label')}</span>
                </label>
              </div>
            )}
            <div className={`${FIELD} flex-[1_1_90px] min-w-[64px] ${FIELD_RESP}`}>
              <div className={FIELD_LABEL}>
                <UserSquare2 className="label-icon" size={9} /> {t('dub.style')}{' '}
                <span className="text-[0.52rem] text-fg-subtle italic ml-[2px]">
                  {t('dub.optional')}
                </span>
              </div>
              <input
                className={FIELD_INPUT}
                placeholder={t('dub.style_placeholder')}
                value={dubInstruct}
                onChange={(e) => setDubInstruct(e.target.value)}
              />
            </div>
            <div className={`${FIELD} basis-full pt-[3px] border-t border-transparent mt-[1px]`}>
              <label className="flex items-center gap-[6px] text-[0.65rem] text-[var(--chrome-fg-muted)] cursor-pointer mb-[2px]">
                <input
                  type="checkbox"
                  className="accent-[var(--color-brand)] cursor-pointer"
                  checked={multiLangMode}
                  onChange={(e) => setMultiLangMode(e.target.checked)}
                />
                <span>{t('dub.multi_lang')}</span>
              </label>
              {multiLangMode && (
                <MultiLangPicker
                  selected={multiLangs}
                  onChange={setMultiLangs}
                  disabled={dubStep === 'generating'}
                  progressByCode={multiLangProgress}
                />
              )}
            </div>
          </div>
          <div className="flex justify-end gap-[6px] flex-wrap">
            <Button
              variant="subtle"
              size="sm"
              onClick={() =>
                editSegments(
                  dubSegments.map((s) => ({
                    ...s,
                    text: s.text_original || s.text,
                    translate_error: undefined,
                    translate_degraded: undefined,
                  })),
                )
              }
              disabled={!dubSegments.some((s) => s.text_original && s.text_original !== s.text)}
              title={t('dub.restore_title')}
            >
              {t('dub.restore')}
            </Button>
            <SettingsActions
              t={t}
              onOpenHardsubDialog={onOpenHardsubDialog}
              hardsubRunning={hardsubRunning}
              canHardsub={!!dubJobId}
              cleanupFirst
              translateVariant="primary"
              onTranslate={handleTranslateAll}
              onCleanup={handleCleanupSegments}
              translating={isTranslating}
              canTranslate={isTranslating || !dubSegments.length}
              canCleanup={!dubSegments.length || !dubJobId}
              hasAny={hasAnyTranslation}
            />
          </div>
        </div>
      )}
    </div>
  );
}
