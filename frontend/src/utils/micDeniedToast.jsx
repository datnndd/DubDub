/**
 * micDeniedToast — the guided "microphone access denied" toast.
 *
 * Shown by the dictation/recording pre-flight when the OS reports the mic
 * grant as denied (utils/permissions.js) — in that state getUserMedia can
 * only throw an opaque NotAllowedError, so we skip it and walk the user to
 * the fix instead: the per-OS hint (capture.mic_hint_*) plus, inside Tauri,
 * an "Open Settings" button that deep-links the OS microphone-privacy pane.
 * On Linux (no such pane) the deep-link resolves false and the toast falls
 * back to the "use your system sound settings" hint.
 *
 * Same toast-with-action pattern as utils/errorToast.jsx.
 */
import toast from 'react-hot-toast';
import { detectPlatform, micHintKey } from './micError';

export function showMicDeniedGuide(t, platform = detectPlatform()) {
  const message = t('capture.mic_denied_toast', { hint: t(micHintKey(platform)) });
  toast.error(message, { duration: 8000 });
}
