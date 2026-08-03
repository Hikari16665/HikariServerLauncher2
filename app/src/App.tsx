import { useEffect, useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { AnimatePresence } from "framer-motion";
import { useSettings } from "./store/settings";
import Layout from "./components/Layout";
import ToastContainer from "./components/Toast";
import ConfirmDialog from "./components/ConfirmDialog";
import Dashboard from "./pages/Dashboard";
import Servers from "./pages/Servers";
import ServerDetail from "./pages/ServerDetail";
import CreateServer from "./pages/CreateServer";
import Settings from "./pages/Settings";
import About from "./pages/About";
import Onboarding from "./pages/Onboarding";
import Login from "./pages/Login";
import Market from "./pages/Market";
import Addons from "./pages/Addons";
import Diagnostics from "./pages/Diagnostics";
import ImportServer from "./pages/ImportServer";
import { api } from "./lib/api";

function AppRoutes() {
  const { onboardingDone, token } = useSettings();
  const [checkingSession, setCheckingSession] = useState(Boolean(token));

  useEffect(() => {
    let active = true;
    if (!token) {
      setCheckingSession(false);
      return;
    }
    setCheckingSession(true);
    api.get<{ valid: boolean }>("/api/auth/verify")
      .catch(() => undefined)
      .finally(() => { if (active) setCheckingSession(false); });
    return () => { active = false; };
  }, [token]);

  if (!onboardingDone) {
    return (
      <Routes>
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="*" element={<Navigate to="/onboarding" replace />} />
      </Routes>
    );
  }

  if (!token) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  if (checkingSession) {
    return <div className="session-check"><span className="loading-spinner" /><strong>正在连接 HSL2 后端…</strong></div>;
  }

  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="servers" element={<Servers />} />
        <Route path="servers/:uuid" element={<ServerDetail />} />
        <Route path="install" element={<CreateServer />} />
        <Route path="import" element={<ImportServer />} />
        <Route path="market" element={<Market />} />
        <Route path="addons" element={<Addons />} />
        <Route path="diagnostics" element={<Diagnostics />} />
        <Route path="settings" element={<Settings />} />
        <Route path="about" element={<About />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <>
      <ToastContainer />
      <ConfirmDialog />
      <AnimatePresence mode="wait">
        <AppRoutes />
      </AnimatePresence>
    </>
  );
}
