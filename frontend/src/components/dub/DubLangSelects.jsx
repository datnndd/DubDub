import React from 'react';
import { useTranslation } from 'react-i18next';
import { Globe, Languages } from 'lucide-react';
import { LANG_CODES } from '../../utils/languages';

// One source of truth for the source/target language selects on the Dub
// landing states. This pair used to be copy-pasted per layout and had already
// drifted (different option separators, inconsistent disabled handling).
// `variant` only picks the surrounding layout + select styling:
//   bar     — compact inline labels (the "has file" bar)
//   landing — the landing-page options row
//   ghost   — flex-1 labelled fields in the editor preview skeleton
const SELECT_CLS = {
  bar: 'px-2 py-1 text-xs rounded-md border border-[var(--border,#3c3836)] bg-[var(--input-bg,#282828)] text-[color:var(--chrome-fg,#ebdbb2)] cursor-pointer focus:border-[var(--color-brand,#fabd2f)] focus:outline-none',
  landing: 'input-base text-[0.65rem]',
  ghost: 'input-base text-[0.68rem]',
};

export default function DubLangSelects({
  variant = 'bar',
  sourceValue,
  targetValue,
  onSourceChange,
  onTargetChange, // (code, label | undefined)
  disabled = false,
  sourceTestId,
  targetTestId,
}) {
  const { t } = useTranslation();
  const cls = SELECT_CLS[variant] || SELECT_CLS.bar;

  const sourceSelect = (testid) => (
    <select
      className={cls}
      value={sourceValue || 'auto'}
      disabled={disabled}
      onChange={(e) => onSourceChange?.(e.target.value)}
      data-testid={testid}
    >
      <option value="auto">🌐 {t('dub.auto')}</option>
      {LANG_CODES.map((lc) => (
        <option key={lc.code} value={lc.code}>
          {lc.label} ({lc.code})
        </option>
      ))}
    </select>
  );

  const targetSelect = (testid) => (
    <select
      className={cls}
      value={targetValue}
      disabled={disabled}
      onChange={(e) => {
        const lc = LANG_CODES.find((l) => l.code === e.target.value);
        onTargetChange?.(e.target.value, lc?.label);
      }}
      data-testid={testid}
    >
      {LANG_CODES.map((lc) => (
        <option key={lc.code} value={lc.code}>
          {lc.label} ({lc.code})
        </option>
      ))}
    </select>
  );

  if (variant === 'ghost') {
    return (
      <>
        <div className="flex-1 min-w-[100px]">
          <div className="label-row text-xs text-[var(--chrome-fg-muted)]">
            <Globe className="label-icon" size={10} /> {t('dub.source_language')}
          </div>
          {sourceSelect(sourceTestId)}
        </div>
        <div className="flex-1 min-w-[100px]">
          <div className="label-row text-xs text-[var(--chrome-fg-muted)]">
            <Languages className="label-icon" size={10} /> {t('dub.target_language')}
          </div>
          {targetSelect(targetTestId)}
        </div>
      </>
    );
  }

  if (variant === 'landing') {
    return (
      <>
        <label className="dub-landing-opts__lang inline-flex items-center gap-[7px] min-w-0 text-[var(--chrome-fg-muted)]">
          <Globe size={13} />
          <span className="text-[0.72rem] font-medium whitespace-nowrap">
            {t('dub.source_language')}:
          </span>
          {sourceSelect(sourceTestId)}
        </label>
        <label className="dub-landing-opts__lang inline-flex items-center gap-[7px] min-w-0 text-[var(--chrome-fg-muted)]">
          <Languages size={13} />
          <span className="text-[0.72rem] font-medium whitespace-nowrap">
            {t('dub.target_language')}:
          </span>
          {targetSelect(targetTestId)}
        </label>
      </>
    );
  }

  return (
    <>
      <label className="inline-flex items-center gap-[5px] text-[12px] text-[var(--muted,#a89984)] whitespace-nowrap">
        <Globe size={13} className="text-[var(--chrome-fg-muted)]" />
        <span className="font-medium text-[color:var(--chrome-fg,#ebdbb2)]">
          {t('dub.source_language')}:
        </span>
        {sourceSelect(sourceTestId)}
      </label>
      <label className="inline-flex items-center gap-[5px] text-[12px] text-[var(--muted,#a89984)] whitespace-nowrap">
        <Languages size={13} className="text-[var(--chrome-fg-muted)]" />
        <span className="font-medium text-[color:var(--chrome-fg,#ebdbb2)]">
          {t('dub.target_language')}:
        </span>
        {targetSelect(targetTestId)}
      </label>
    </>
  );
}
