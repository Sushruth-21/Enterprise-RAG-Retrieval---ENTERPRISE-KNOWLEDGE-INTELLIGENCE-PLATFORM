import { create } from 'zustand';
import { UserSettings } from '@/types';
import { useAuthStore } from './useAuthStore';

interface SettingsState {
  settings: UserSettings;
  updateSettings: (patch: Partial<UserSettings>) => boolean;
  resetSettings: () => void;
}

const defaultSettings: UserSettings = {
  theme: 'dark',
  streamingSpeed: 'fast',
  groundingStrictness: 'strict',
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  useMockApi: true,
  reducedMotion: false,
};

export const useSettingsStore = create<SettingsState>((set) => ({
  settings: defaultSettings,
  updateSettings: (patch) => {
    // If attempting to modify critical backend target without admin privileges, block
    if (patch.apiBaseUrl !== undefined && !useAuthStore.getState().isAdmin()) {
      useAuthStore.getState().openAdminModal();
      return false;
    }

    set((state) => ({
      settings: { ...state.settings, ...patch },
    }));
    return true;
  },
  resetSettings: () => set({ settings: defaultSettings }),
}));
