import { lazy, Suspense, useEffect, useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { AnimatePresence } from "framer-motion";
import { useSettings } from "./store/settings";
import Layout from "./components/Layout";
import WorkspaceLayout from "./components/WorkspaceLayout";
import WorkspaceOrb from "./components/WorkspaceOrb";
import WorkspaceMenu from "./components/WorkspaceMenu";
import ToastContainer from "./components/Toast";
import ConfirmDialog from "./components/ConfirmDialog";
import { api } from "./lib/api";
import { useWorkspaceSession } from "./hooks/useWorkspaceSession";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const Servers = lazy(() => import("./pages/Servers"));
const ServerDetail = lazy(() => import("./pages/ServerDetail"));
const CreateServer = lazy(() => import("./pages/CreateServer"));
const Settings = lazy(() => import("./pages/Settings"));
const About = lazy(() => import("./pages/About"));
const Onboarding = lazy(() => import("./pages/Onboarding"));
const Login = lazy(() => import("./pages/Login"));
const Market = lazy(() => import("./pages/Market"));
const Addons = lazy(() => import("./pages/Addons"));
const Diagnostics = lazy(() => import("./pages/Diagnostics"));
const ImportServer = lazy(() => import("./pages/ImportServer"));
const Tasks = lazy(() => import("./pages/Tasks"));

function PageFallback() {
  return (
    <div className="session-check" role="status" aria-live="polite">
      <span className="loading-spinner" />
      <strong>正在加载页面…</strong>
    </div>
  );
}

function AppRoutes() {
  const windowParams = new URLSearchParams(window.location.search);
  const windowView = windowParams.get("view");
  const workspaceRoute = windowParams.get("route");
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
      <Route path="/" element={windowView === "workspace" ? <WorkspaceLayout /> : <Layout />}>
        <Route
          index
          element={
            windowView === "workspace" && workspaceRoute
              ? <Navigate to={workspaceRoute} replace />
              : <Dashboard />
          }
        />
        <Route path="servers" element={<Servers />} />
        <Route path="servers/:uuid" element={<ServerDetail />} />
        <Route path="install" element={<CreateServer />} />
        <Route path="import" element={<ImportServer />} />
        <Route path="market" element={<Market />} />
        <Route path="addons" element={<Addons />} />
        <Route path="diagnostics" element={<Diagnostics />} />
        <Route path="settings" element={<Settings />} />
        <Route path="about" element={<About />} />
        <Route path="tasks" element={<Tasks />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  useWorkspaceSession();
  const windowView = new URLSearchParams(window.location.search).get("view");
  if (windowView === "orb") return <WorkspaceOrb />;
  if (windowView === "menu") return <WorkspaceMenu />;
  return (
    <>
      <ToastContainer />
      <ConfirmDialog />
      <AnimatePresence mode="wait">
        <Suspense fallback={<PageFallback />}>
          <AppRoutes />
        </Suspense>
      </AnimatePresence>
    </>
  );
}
