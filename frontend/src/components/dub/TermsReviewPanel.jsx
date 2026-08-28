import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, BookOpen, Languages, Plus, RefreshCw, Trash2, X } from 'lucide-react';
import { Button, Input, Textarea } from '../../ui';
import { dubTranslateContext } from '../../api/dub';

// Pre-translation brief review. The backend's /dub/translate-context drafts
// a theme summary + terminology map from the transcript (one LLM pass,
// fingerprint-cached on the job); the user edits it here and only then
// starts the translation — the reviewed brief rides back on /dub/translate
// as translation_context and replaces the hidden auto-extraction.

const SHELL =
  'rounded-[var(--chrome-radius-pill)] border border-[var(--chrome-border)] bg-[var(--chrome-bg)]';
const HEAD =
  'font-[family-name:var(--chrome-font-mono)] text-[length:var(--chrome-label-size)] tracking-[var(--chrome-label-track)] uppercase text-[var(--chrome-fg-muted)] font-semibold';
const LABEL =
  'block mb-[2px] font-[family-name:var(--chrome-font-mono)] text-[length:var(--chrome-label-size)] tracking-[var(--chrome-label-track)] uppercase text-[var(--chrome-fg-muted)]';
const PILL =
  'px-[6px] py-[1px] rounded-full text-[0.58rem] uppercase tracking-[var(--chrome-label-track)] bg-[var(--chrome-hover-bg)] text-[var(--chrome-fg-muted)]';

export default function TermsReviewPanel({
  jobId,
  targetLang,
  segments = [],
  translating = false,
  onTranslate,
  onClose,
}) {
  const { t } = useTranslation();
  const [status, setStatus] = useState('extracting'); // extracting | ready | error
  const [extracting, setExtracting] = useState(false);
  const [theme, setTheme] = useState('');
  const [terms, setTerms] = useState([]);
  const [error, setError] = useState('');
  const [cached, setCached] = useState(false);
  const [dirty, setDirty] = useState(false);

  const extract = useCallback(
    async (force = false) => {
      if (!segments.length || !targetLang) return;
      setExtracting(true);
      setError('');
      try {
        const res = await dubTranslateContext({
          job_id: jobId || undefined,
          target_lang: targetLang,
          force: force || undefined,
          segments: segments.map((s) => ({
            id: String(s.id),
            // Same original-text rule as /dub/translate: edits already made to
            // the source transcript are what the brief should describe.
            text: s.text_original && s.text_original.trim() ? s.text_original : s.text,
          })),
        });
        setTheme(res.theme || '');
        setTerms(
          (res.terms || []).map((x) => ({
            source: x.source || '',
            target: x.target || '',
            note: x.note || '',
          })),
        );
        setCached(!!res.cached);
        setDirty(false);
        setStatus('ready');
      } catch (e) {
        setError(String(e?.message || e));
        setStatus('error');
      } finally {
        setExtracting(false);
      }
    },
    // Segment identity is stable enough at the moments this runs (mount and
    // manual re-extract); a live dep here would re-draft on every keystroke
    // made in the segment table while the panel is open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [jobId, targetLang],
  );

  useEffect(() => {
    extract(false);
  }, [extract]);

  const editTheme = (value) => {
    setTheme(value);
    setDirty(true);
  };
  const editTerm = (index, key, value) => {
    setTerms((prev) => prev.map((row, i) => (i === index ? { ...row, [key]: value } : row)));
    setDirty(true);
  };
  const addTerm = () => {
    setTerms((prev) => [...prev, { source: '', target: '', note: '' }]);
    setDirty(true);
  };
  const removeTerm = (index) => {
    setTerms((prev) => prev.filter((_, i) => i !== index));
    setDirty(true);
  };
  const reextract = () => {
    if (dirty && !window.confirm(t('terms_review.re_extract_confirm'))) return;
    extract(true);
  };
  const start = () => {
    if (!onTranslate || extracting || translating) return;
    onTranslate({ theme: theme.trim(), terms });
  };

  return (
    <div className={`${SHELL} px-[var(--space-3)] py-[8px]`} data-testid="terms-review-panel">
      <div className="flex items-center justify-between gap-[6px] mb-[6px]">
        <div className="flex items-center gap-[6px] min-w-0">
          <BookOpen size={12} className="text-[var(--chrome-fg-muted)] shrink-0" />
          <span className={HEAD}>{t('terms_review.title')}</span>
          {dirty && <span className={PILL}>{t('terms_review.edited')}</span>}
          {!dirty && cached && status === 'ready' && (
            <span className={PILL}>{t('terms_review.cached')}</span>
          )}
        </div>
        <div className="flex items-center gap-[2px] shrink-0">
          <Button
            variant="ghost"
            size="sm"
            onClick={reextract}
            disabled={extracting || translating}
            title={t('terms_review.re_extract')}
          >
            <RefreshCw size={10} className={extracting ? 'animate-spin' : undefined} />
          </Button>
          <Button variant="ghost" size="sm" onClick={onClose} title={t('terms_review.close_title')}>
            <X size={10} />
          </Button>
        </div>
      </div>

      {status === 'error' ? (
        <div>
          <p className="flex items-center gap-[6px] text-[length:var(--text-xs)] text-[var(--chrome-fg)] mb-[6px]">
            <AlertTriangle size={12} className="text-[#fabd2f] shrink-0" />
            <span className="font-semibold">{t('terms_review.extract_error')}</span>
          </p>
          <p className="text-[length:var(--text-xs)] text-[var(--chrome-fg-muted)] leading-[1.5] mb-[8px] break-words">
            {error}
          </p>
          <div className="flex items-center gap-[6px] flex-wrap">
            <Button variant="subtle" size="sm" onClick={() => extract(true)} disabled={extracting}>
              {t('terms_review.re_extract')}
            </Button>
            <Button
              variant="subtle"
              size="sm"
              onClick={() => onTranslate?.(null)}
              disabled={translating}
              loading={translating}
              leading={!translating && <Languages size={10} />}
            >
              {t('terms_review.translate_without')}
            </Button>
          </div>
        </div>
      ) : (
        <div>
          <p className="text-[length:var(--text-xs)] text-[var(--chrome-fg-muted)] leading-[1.5] mb-[8px]">
            {t('terms_review.subtitle')}
          </p>
          <label className={LABEL}>{t('terms_review.theme_label')}</label>
          <Textarea
            value={theme}
            rows={2}
            placeholder={t('terms_review.theme_placeholder')}
            onChange={(e) => editTheme(e.target.value)}
            disabled={extracting}
            className="w-full mb-[8px] text-[length:var(--text-xs)]"
          />
          <label className={LABEL}>{t('terms_review.terms_label')}</label>
          {terms.length === 0 && !extracting && (
            <p className="text-[length:var(--text-xs)] text-[var(--chrome-fg-dim)] mb-[4px]">
              {t('terms_review.terms_empty')}
            </p>
          )}
          <div className="flex flex-col gap-[4px] mb-[6px]">
            {terms.map((row, i) => (
              <div key={i} className="flex items-center gap-[4px]">
                <Input
                  value={row.source}
                  placeholder={t('terms_review.term_source_placeholder')}
                  disabled={extracting}
                  onChange={(e) => editTerm(i, 'source', e.target.value)}
                  className="flex-1 min-w-0 !text-[0.65rem] !px-[6px] !py-[3px]"
                />
                <span className="text-[var(--chrome-fg-dim)] text-[0.65rem]">→</span>
                <Input
                  value={row.target}
                  placeholder={t('terms_review.term_target_placeholder')}
                  disabled={extracting}
                  onChange={(e) => editTerm(i, 'target', e.target.value)}
                  className="flex-1 min-w-0 !text-[0.65rem] !px-[6px] !py-[3px]"
                />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => removeTerm(i)}
                  disabled={extracting}
                  title={t('terms_review.remove_term_title')}
                >
                  <Trash2 size={10} />
                </Button>
              </div>
            ))}
          </div>
          <button
            type="button"
            className="inline-flex items-center gap-[4px] mb-[10px] text-[length:var(--text-xs)] text-[var(--chrome-fg-muted)] hover:text-[var(--chrome-fg)] cursor-pointer bg-transparent border border-transparent"
            onClick={addTerm}
            disabled={extracting}
          >
            <Plus size={10} /> {t('terms_review.add_term')}
          </button>
          <div className="flex items-center gap-[8px] flex-wrap">
            <Button
              variant="primary"
              size="sm"
              onClick={start}
              disabled={extracting}
              loading={translating}
              leading={!translating && <Languages size={10} />}
            >
              {t('terms_review.start_translation')}
            </Button>
            {extracting && (
              <span className="text-[length:var(--text-xs)] text-[var(--chrome-fg-muted)]">
                {t('terms_review.extracting')}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
