import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { HashRouter } from "react-router-dom";
import "./index.css";
import App from "./App";
import { applyTheme } from "./lib/themes";
import { useSettings } from "./store/settings";
import { listen } from "@tauri-apps/api/event";

document.addEventListener("contextmenu", (e) => e.preventDefault());

const windowView = new URLSearchParams(window.location.search).get("view");
if (windowView === "orb" || windowView === "menu") {
  document.documentElement.classList.add("transparent-window");
  document.body.classList.add("transparent-window");
  document.documentElement.style.backgroundColor = "transparent";
  document.body.style.backgroundColor = "transparent";
}

// Restore persisted theme on load
const savedTheme = useSettings.getState().theme;
if (savedTheme) {
  applyTheme(savedTheme);
}

useSettings.subscribe((state, previous) => {
  if (state.theme !== previous.theme) applyTheme(state.theme);
});

listen<{ theme: string }>("theme-changed", ({ payload }) => {
  if (!payload?.theme) return;
  useSettings.setState({ theme: payload.theme });
  applyTheme(payload.theme);
}).catch(() => undefined);

window.addEventListener("storage", (event) => {
  if (event.key !== "hsl-settings" || !event.newValue) return;
  try {
    const theme = JSON.parse(event.newValue)?.state?.theme;
    if (typeof theme === "string") {
      useSettings.setState({ theme });
      applyTheme(theme);
    }
  } catch { /* ignore invalid persisted data */ }
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <HashRouter>
      <App />
    </HashRouter>
  </StrictMode>
);
