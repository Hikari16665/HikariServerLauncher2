import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { HashRouter } from "react-router-dom";
import "./index.css";
import App from "./App";
import { applyTheme } from "./lib/themes";
import { useSettings } from "./store/settings";

document.addEventListener("contextmenu", (e) => e.preventDefault());

// Restore persisted theme on load
const savedTheme = useSettings.getState().theme;
if (savedTheme) {
  applyTheme(savedTheme);
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <HashRouter>
      <App />
    </HashRouter>
  </StrictMode>
);
