import { useTranslation } from 'react-i18next';

export function detectHints(message = '', logs = []) {
  const text = `${message} ${logs.map((l) => (typeof l === 'string' ? l : l?.line || l?.message || '')).join(' ')}`;
  if (/intel mac|x86_64/i.test(text)) {
    return ['bootstrap.hint_intel_mac'];
  }
  if (/port\s*3900|address.*in use|port.*in use|exit code 78|errno\s*(?:10048|48|98)\b/i.test(text)) {
    return ['bootstrap.hint_port'];
  }
  return ['bootstrap.hint_default'];
}

export function isUnrecoverableFailure(message = '', logs = []) {
  const text = `${message} ${logs.map((l) => (typeof l === 'string' ? l : l?.line || l?.message || '')).join(' ')}`;
  return /intel mac|x86_64|unsupported architecture|requires macos|requires windows/i.test(text);
}

/** Web deployments are started by FastAPI/Vite or Docker, so no desktop
 * bootstrap lifecycle exists. Keep the small interface used by App while the
 * browser waits for its ordinary HTTP health probe. */
export function useBootstrapStage() {
  return { stage: 'ready', message: null };
}

export function BootstrapSplash({ message }) {
  const { t } = useTranslation();
  return (
    <div className="app-bootstrap-scale" role="status">
      {message || t('app.loading')}
    </div>
  );
}

export default BootstrapSplash;
