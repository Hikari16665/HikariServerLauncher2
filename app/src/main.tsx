import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { HashRouter } from "react-router-dom";
import "./index.css";
import App from "./App";
import { applyTheme } from "./lib/themes";
import { useSettings } from "./store/settings";

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

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <HashRouter>
      <App />
    </HashRouter>
  </StrictMode>
);
