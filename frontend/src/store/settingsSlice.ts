import { StateCreator } from 'zustand';

export interface SettingsSlice {
  isSettingsOpen: boolean;
  settingsActiveTab: 'providers' | 'storage' | 'general';
  settingsTargetProvider: string | null;
  setSettingsOpen: (open: boolean) => void;
  setSettingsActiveTab: (tab: 'providers' | 'storage' | 'general') => void;
  setSettingsTargetProvider: (id: string | null) => void;
  openSettings: (tab?: 'providers' | 'storage' | 'general', providerId?: string | null) => void;
}

export const createSettingsSlice: StateCreator<SettingsSlice, [], [], SettingsSlice> = (set) => ({
  isSettingsOpen: false,
  settingsActiveTab: 'providers',
  settingsTargetProvider: null,
  setSettingsOpen: (open) => set({ isSettingsOpen: open }),
  setSettingsActiveTab: (tab) => set({ settingsActiveTab: tab }),
  setSettingsTargetProvider: (id) => set({ settingsTargetProvider: id }),
  openSettings: (tab = 'providers', providerId = null) =>
    set({
      isSettingsOpen: true,
      settingsActiveTab: tab,
      settingsTargetProvider: providerId,
    }),
});
