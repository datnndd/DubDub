if (import.meta.env.DEV && !window.__vite_plugin_react_preamble_installed__) {
  const RefreshRuntime = await import('/@react-refresh');
  RefreshRuntime.default.injectIntoGlobalHook(window);
  window.$RefreshReg$ = () => {};
  window.$RefreshSig$ = () => (type) => type;
  window.__vite_plugin_react_preamble_installed__ = true;
}

// Web-platform gap fills for the oldest WebView we support (macOS 13.3 ships
// WKWebView 16.4; Linux takes whatever WebKitGTK the distro has, which is the
// version we cannot pin). MUST be first: these are touched during the first React
// render, so a missing one throws mid-render and leaves a dead window rather
// than a degraded feature (#1245).
import './utils/webCompat.js';

// AudioContext autoplay-policy unlock — MUST install before any module that
// constructs an AudioContext (wavesurfer.js, the AEC tap, the dictation
// capture, etc.). The side-effecting import patches `window.AudioContext`
// to track every instance ever created; `installAudioUnlock()` then wires
// a one-time pointerdown/keydown listener that resumes them all on the
// first user gesture. Without this, Linux Firefox/Chrome and Android Chrome
// leave WaveSurfer's AudioContext suspended → peaks decode hangs → `ready`
// never fires → play button stays disabled → no /audio/ request ever fires.
import { installAudioUnlock } from './utils/audioUnlock.js';
installAudioUnlock();

const { bootstrapApp } = await import('./main-app.jsx');

bootstrapApp();

// #380: after an app update, a still-open window can hold an index.html whose
// lazy chunks reference old hashed assets that no longer exist on disk —
// vite surfaces that as "Unable to preload CSS for /assets/…". The documented
// recovery is a one-time reload to pick up the fresh manifest. The session
// flag prevents a reload loop if the asset is genuinely missing.
window.addEventListener('vite:preloadError', (event) => {
  if (sessionStorage.getItem('omnivoice.preloadErrorReloaded') === '1') return;
  sessionStorage.setItem('omnivoice.preloadErrorReloaded', '1');
  event.preventDefault();
  window.location.reload();
});
