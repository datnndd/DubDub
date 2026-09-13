import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
// Fonts load before tokens so --font-* can resolve immediately (no FOUT).
// Inter ships as a single variable file; Source Serif 4 too. Plex Mono has
// no variable build so we pull the three weights we use (400/500/600).
import '@fontsource-variable/inter';
import '@fontsource/ibm-plex-mono/400.css';
import '@fontsource/ibm-plex-mono/500.css';
import '@fontsource/ibm-plex-mono/600.css';
import '@fontsource-variable/source-serif-4';
import './i18n'; // ← initialise i18next before any component renders
import './ui';
// Single stylesheet: index.css now carries the Tailwind foundation, the token
// scale + themes, and every former per-component .css (residual + all component
// styles) consolidated in, so this one import pulls in the whole app's CSS.
import './index.css';
import App from './App.jsx';
import ErrorBoundary from './components/ErrorBoundary';
import RemoteAuthGate from './components/RemoteAuthGate';
import { installConsoleCapture } from './utils/consoleBuffer.js';
import { installGlobalErrorHandlers } from './utils/globalErrorHandlers.js';

installConsoleCapture();
// After console capture so the underlying console.error of each uncaught
// failure is already in the ring buffer when the toast appears.
installGlobalErrorHandlers();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export async function bootstrapApp() {
  const root = createRoot(document.getElementById('root'));
  root.render(
    <StrictMode>
      {/* Root error boundary: a throw before a tab-level boundary mounts must
          still render an in-app recovery card rather than leave #root blank. */}
      <ErrorBoundary name="app-root">
        <QueryClientProvider client={queryClient}>
          {/* RemoteAuthGate is the TRUE outermost wrap so a remote device that
            loads a bare URL (no ?pin=) during first-run setup states —
            setup-status check, SetupWizard, BootstrapSplash — still gets the
            PIN dialog instead of a silent 401. Loopback / QR users are
            unaffected (the gate only shows on an ov:auth-required event). */}
          <RemoteAuthGate>
            <App />
          </RemoteAuthGate>
        </QueryClientProvider>
      </ErrorBoundary>
    </StrictMode>,
  );
  return root;
}
