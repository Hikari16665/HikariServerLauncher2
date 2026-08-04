import { create } from "zustand";
import { persist } from "zustand/middleware";
import { invoke } from "@tauri-apps/api/core";

function syncWorkspaceSession(token: string) {
  invoke("set_workspace_session", { token }).catch(() => undefined);
}

interface SettingsState {
  apiUrl: string;
  adminKey: string;
  token: string;
  tokenExpiry: number;
  useMirror: boolean;
  onboardingDone: boolean;
  theme: string;
  setApiUrl: (url: string) => void;
  setAdminKey: (key: string) => void;
  setAuth: (token: string, adminKey: string) => void;
  setToken: (token: string) => void;
  hydrateToken: (token: string) => void;
  setUseMirror: (v: boolean) => void;
  setOnboardingDone: () => void;
  setTheme: (theme: string) => void;
  clearAuth: () => void;
}

export const useSettings = create<SettingsState>()(
  persist(
    (set) => ({
      apiUrl: "http://127.0.0.1:5000",
      adminKey: "",
      token: "",
      tokenExpiry: 0,
      useMirror: false,
      onboardingDone: false,
      theme: "softPink",
      setApiUrl: (url) => set({ apiUrl: url }),
      setAdminKey: (key) => set({ adminKey: key }),
      setAuth: (token, adminKey) =>
        set(() => { syncWorkspaceSession(token); return { token, adminKey, tokenExpiry: Date.now() + 43200 * 1000 }; }),
      setToken: (token) =>
        set(() => { syncWorkspaceSession(token); return { token, tokenExpiry: Date.now() + 43200 * 1000 }; }),
      hydrateToken: (token) => set({ token, tokenExpiry: token ? Date.now() + 43200 * 1000 : 0 }),
      setUseMirror: (v) => set({ useMirror: v }),
      setOnboardingDone: () => set({ onboardingDone: true }),
      setTheme: (theme) => set({ theme }),
      clearAuth: () => set(() => { syncWorkspaceSession(""); return { token: "", adminKey: "", tokenExpiry: 0 }; }),
    }),
    {
      name: "hsl-settings",
      // Keep credentials in memory only; localStorage is not a secret store.
      partialize: (state) => ({
        apiUrl: state.apiUrl,
        useMirror: state.useMirror,
        onboardingDone: state.onboardingDone,
        theme: state.theme,
      }),
    }
  )
);
