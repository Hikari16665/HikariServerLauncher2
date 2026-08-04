import { useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useSettings } from "../store/settings";

export function useWorkspaceSession() {
  const token = useSettings((state) => state.token);
  const hydrateToken = useSettings((state) => state.hydrateToken);
  useEffect(() => {
    let active = true;
    const synchronize = async () => {
      try {
        const session = await invoke<{ token: string }>("get_workspace_session");
        if (active && session.token !== useSettings.getState().token) hydrateToken(session.token);
      } catch {}
    };
    synchronize();
    const timer = window.setInterval(synchronize, 750);
    return () => { active = false; clearInterval(timer); };
  }, [hydrateToken, token]);
}
