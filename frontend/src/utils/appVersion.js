/* global __APP_VERSION__ -- injected by Vite (vite.config define) at build time */
// The build's own version remains available when the backend is unreachable.
export const APP_VERSION = (typeof __APP_VERSION__ !== 'undefined' && __APP_VERSION__) || 'unknown';

/**
 * Resolve the version shown in Settings → About / the diagnostics block. Prefer
 * the supplied app version, then the live backend's `/system/info`
 * `app_version`, then the build-time constant, so it is never blank.
 *
 * @param {string|null|undefined} appVersion  optional runtime version
 * @param {{ app_version?: string }|null|undefined} info  `/system/info` payload
 * @returns {string}
 */
export function resolveAboutVersion(appVersion, info) {
  return appVersion || info?.app_version || APP_VERSION;
}

/**
 * Whether the one-time "What's new in vX" affordance should show
 * (feat/safe-updates): only when a previous version was recorded AND it
 * differs from the running build. A fresh profile (`seenVersion == null`)
 * must baseline silently instead — brand-new users shouldn't be nudged to
 * read notes for the version they just installed. An 'unknown' build version
 * (dev without the Vite define) never triggers it.
 *
 * @param {string|null|undefined} seenVersion  last version whose notes were seen
 * @param {string|null|undefined} currentVersion  the running build's version
 * @returns {boolean}
 */
export function whatsNewPending(seenVersion, currentVersion) {
  return (
    Boolean(seenVersion) &&
    Boolean(currentVersion) &&
    currentVersion !== 'unknown' &&
    seenVersion !== currentVersion
  );
}
