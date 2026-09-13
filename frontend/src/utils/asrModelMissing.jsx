/**
 * asrModelMissing — typed "ASR requires configuration" error + CTA.
 *
 * VoiceStudio operates strictly with Deepgram Cloud ASR. If unconfigured,
 * backends respond with a typed payload:
 *
 *   HTTP 409  { detail: { error: 'asr_model_missing', ... } }
 *   SSE error { detail, error: 'asr_model_missing', ... }
 *   WS frame  { type: 'error', kind: 'asr_model_missing', ... }
 *
 * `asrMissingPayload` normalizes all shapes.
 * `toastAsrModelMissing` directs the user to configure Deepgram API key in Settings.
 */
import toast from 'react-hot-toast';
import i18next from 'i18next';
import { useAppStore } from '../store';

export const ASR_MODEL_MISSING = 'asr_model_missing';

/** Extract the typed payload from any of the transport shapes, or null. */
export function asrMissingPayload(err) {
  if (!err || typeof err !== 'object') return null;
  // Error tagged by the dub SSE handler.
  if (err.asrModelMissing && typeof err.asrModelMissing === 'object') return err.asrModelMissing;
  // Raw SSE data / WS frame.
  if (err.error === ASR_MODEL_MISSING) return err;
  // ApiError from apiFetch: structured 409 detail.
  const d = err.detail;
  if (d && typeof d === 'object' && d.error === ASR_MODEL_MISSING) return d;
  return null;
}

/** Actionable toast: directs user to configure Deepgram API key in Settings. */
export function toastAsrModelMissing(payload) {
  const t = i18next.t.bind(i18next);
  const message =
    payload?.detail ||
    t('asr_missing.message', {
      defaultValue: 'Deepgram Cloud ASR requires an API key. Configure it in Settings.',
    });
  toast.error(
    (tst) => (
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ flex: 1 }}>{message}</span>
        <button
          type="button"
          className="btn-secondary"
          style={{ flexShrink: 0, whiteSpace: 'nowrap' }}
          onClick={() => {
            toast.dismiss(tst.id);
            useAppStore.getState().openSettingsTab?.('engines');
          }}
        >
          {t('settings.title', { defaultValue: 'Settings' })}
        </button>
      </div>
    ),
    { duration: 10000 },
  );
}

