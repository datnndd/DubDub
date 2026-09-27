import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';
import { useDubDubStore } from '../store';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error caught by ErrorBoundary:', error, errorInfo);
    this.setState({ errorInfo });
  }

  private handleRecover = () => {
    try {
      const store = useDubDubStore.getState();
      if (typeof store.setStep === 'function') {
        store.setStep(1);
      }
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem('dubdub_active_project_id');
      }
    } catch (_) {}
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  private handleReload = () => {
    if (typeof window !== 'undefined') {
      window.location.reload();
    }
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex-1 w-full h-full min-h-[360px] flex items-center justify-center p-6 bg-[#F9F8F5]">
          <div className="max-w-md w-full bg-white rounded-2xl border border-stone-200 shadow-xl p-6 flex flex-col items-center text-center">
            <div className="w-12 h-12 rounded-2xl bg-amber-50 border border-amber-200 flex items-center justify-center text-[#8D4B00] mb-4 shadow-2xs">
              <AlertTriangle className="w-6 h-6" />
            </div>

            <h3 className="font-bold text-stone-900 text-base mb-1.5">
              {this.props.fallbackTitle || 'Something went wrong rendering this section'}
            </h3>

            <p className="text-xs text-stone-500 mb-4 leading-relaxed">
              {this.state.error?.message || 'An unexpected rendering error occurred. You can safely return to Stage 1 or reload.'}
            </p>

            {this.state.error && (
              <div className="w-full text-left bg-stone-50 rounded-lg p-2.5 mb-4 border border-stone-200/80 font-mono text-[10px] text-stone-600 max-h-24 overflow-y-auto">
                {this.state.error.toString()}
              </div>
            )}

            <div className="flex items-center gap-2.5 w-full">
              <button
                type="button"
                onClick={this.handleRecover}
                className="flex-1 py-2 px-3 rounded-lg bg-[#8D4B00] hover:bg-[#743D00] text-white text-xs font-bold flex items-center justify-center gap-1.5 shadow-2xs transition-colors cursor-pointer"
              >
                <Home className="w-3.5 h-3.5" />
                <span>Return to Stage 1</span>
              </button>

              <button
                type="button"
                onClick={this.handleReload}
                className="py-2 px-3 rounded-lg bg-stone-100 hover:bg-stone-200 text-stone-700 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Reload</span>
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
