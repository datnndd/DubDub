import React, { useEffect, useState } from 'react';
import {
  X,
  Settings as SettingsIcon,
  Key,
  HardDrive,
  Sliders,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import { useDubDubStore } from '../../store';
import { fetchSettings, SettingsSnapshot } from '../../api/settingsApi';
import { ApiProvidersTab } from './tabs/ApiProvidersTab';
import { StorageTab } from './tabs/StorageTab';
import { GeneralTab } from './tabs/GeneralTab';

export interface SettingsModalProps {
  forceOpen?: boolean;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ forceOpen }) => {
  const storeOpen = useDubDubStore((s) => s.isSettingsOpen);
  const isOpen = forceOpen !== undefined ? forceOpen : storeOpen;
  const setIsOpen = useDubDubStore((s) => s.setSettingsOpen);
  const activeTab = useDubDubStore((s) => s.settingsActiveTab);
  const setActiveTab = useDubDubStore((s) => s.setSettingsActiveTab);
  const targetProvider = useDubDubStore((s) => s.settingsTargetProvider);

  const [loading, setLoading] = useState(false);
  const [snapshot, setSnapshot] = useState<SettingsSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSettings();
      setSnapshot(data);
      // Immediately sync Zustand store backend options so provider badges and validation update
      await useDubDubStore.getState().initializeBackend();
    } catch (err: any) {
      setError(err.message || 'Failed to load application settings');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = async () => {
    setIsOpen(false);
    await useDubDubStore.getState().initializeBackend();
  };

  useEffect(() => {
    if (isOpen) {
      loadData();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4 animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl shadow-2xl border border-stone-200 max-w-3xl w-full max-h-[90vh] flex flex-col overflow-hidden">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-stone-200 flex items-center justify-between bg-[#FAF9F6] shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-amber-500/15 text-[#8D4B00] flex items-center justify-center border border-amber-500/25 shadow-2xs">
              <SettingsIcon className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-stone-900 leading-tight">Settings &amp; Preferences</h3>
              <p className="text-[11px] text-stone-500 mt-0.5">
                Manage external API credentials, storage locations, and runtime configuration
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={loadData}
              disabled={loading}
              className="p-1.5 rounded-lg text-stone-400 hover:text-stone-700 hover:bg-stone-200/60 transition-colors cursor-pointer"
              title="Refresh settings snapshot"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-[#8D4B00]' : ''}`} />
            </button>
            <button
              onClick={handleClose}
              className="p-1.5 rounded-lg text-stone-400 hover:text-stone-700 hover:bg-stone-200/60 transition-colors cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="px-6 border-b border-stone-200 bg-stone-50/60 shrink-0 flex items-center gap-2 pt-2">
          <button
            onClick={() => setActiveTab('providers')}
            className={`px-3 py-2 text-xs font-bold rounded-t-lg flex items-center gap-2 border-b-2 transition-all cursor-pointer ${
              activeTab === 'providers'
                ? 'border-[#8D4B00] text-[#8D4B00] bg-white shadow-2xs'
                : 'border-transparent text-stone-500 hover:text-stone-800'
            }`}
          >
            <Key className="w-3.5 h-3.5" />
            <span>API Providers</span>
          </button>

          <button
            onClick={() => setActiveTab('storage')}
            className={`px-3 py-2 text-xs font-bold rounded-t-lg flex items-center gap-2 border-b-2 transition-all cursor-pointer ${
              activeTab === 'storage'
                ? 'border-[#8D4B00] text-[#8D4B00] bg-white shadow-2xs'
                : 'border-transparent text-stone-500 hover:text-stone-800'
            }`}
          >
            <HardDrive className="w-3.5 h-3.5" />
            <span>Storage &amp; Paths</span>
          </button>

          <button
            onClick={() => setActiveTab('general')}
            className={`px-3 py-2 text-xs font-bold rounded-t-lg flex items-center gap-2 border-b-2 transition-all cursor-pointer ${
              activeTab === 'general'
                ? 'border-[#8D4B00] text-[#8D4B00] bg-white shadow-2xs'
                : 'border-transparent text-stone-500 hover:text-stone-800'
            }`}
          >
            <Sliders className="w-3.5 h-3.5" />
            <span>General Settings</span>
          </button>
        </div>

        {/* Tab Content Body */}
        <div className="flex-1 min-h-0 overflow-y-auto p-6 bg-[#FAF9F6]/40">
          {loading && !snapshot ? (
            <div className="py-16 flex flex-col items-center justify-center gap-3 text-stone-400">
              <Loader2 className="w-6 h-6 animate-spin text-[#8D4B00]" />
              <span className="text-xs font-medium">Loading configuration snapshot…</span>
            </div>
          ) : error ? (
            <div className="p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs">
              <p className="font-semibold mb-1">Failed to load settings:</p>
              <p>{error}</p>
              <button
                onClick={loadData}
                className="mt-3 px-3 py-1 bg-white border border-rose-300 rounded-lg text-rose-700 font-semibold text-[11px]"
              >
                Retry
              </button>
            </div>
          ) : snapshot ? (
            <>
              <div className={activeTab === 'providers' ? 'block' : 'hidden'}>
                <ApiProvidersTab
                  providers={snapshot.providers}
                  targetProvider={targetProvider}
                  onRefresh={loadData}
                />
              </div>
              <div className={activeTab === 'storage' ? 'block' : 'hidden'}>
                <StorageTab storage={snapshot.storage} onRefresh={loadData} />
              </div>
              <div className={activeTab === 'general' ? 'block' : 'hidden'}>
                <GeneralTab general={snapshot.general} onRefresh={loadData} />
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
};
