import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../lib/api";
import type { Server, ServerStatus } from "../lib/types";
import { useToastStore } from "../store/toast";
import { showConfirm } from "../components/ConfirmDialog";
import Terminal from "../components/Terminal";
import FileBrowser from "../components/FileBrowser";
import ConfigEditor from "../components/ConfigEditor";
import BackupPanel from "../components/BackupPanel";

type Tab = "terminal" | "files" | "config" | "backups";
const TABS: { key: Tab; label: string }[] = [{ key: "terminal", label: "终端" }, { key: "files", label: "文件" }, { key: "config", label: "配置" }, { key: "backups", label: "备份" }];

export default function ServerDetail() {
  const { uuid } = useParams<{ uuid: string }>();
  const navigate = useNavigate();
  const addToast = useToastStore((state) => state.addToast);
  const [server, setServer] = useState<Server | null>(null);
  const [status, setStatus] = useState<ServerStatus | null>(null);
  const [tab, setTab] = useState<Tab>("terminal");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!uuid) return;
    api.get<{ server: Server }>(`/api/servers/${uuid}`).then((data) => setServer(data.server)).catch(() => navigate("/servers")).finally(() => setLoading(false));
  }, [uuid, navigate]);
  useEffect(() => {
    if (!uuid) return;
    const refresh = () => api.get<ServerStatus>(`/api/servers/${uuid}/status`).then(setStatus).catch(() => undefined);
    refresh(); const timer = setInterval(refresh, 3000); return () => clearInterval(timer);
  }, [uuid]);

  async function action(value: "start" | "stop" | "kill") {
    if (!uuid) return;
    try { await api.post(`/api/servers/${uuid}/${value}`); setStatus(await api.get<ServerStatus>(`/api/servers/${uuid}/status`)); }
    catch (error: any) { addToast(error.message || "操作失败", "error", error.detail); }
  }
  async function remove() {
    if (!uuid || !server || !await showConfirm(`确定删除“${server.name}”吗？此操作无法恢复。`)) return;
    try { await api.delete(`/api/servers/${uuid}`); navigate("/servers"); }
    catch (error: any) { addToast(error.message || "删除失败", "error", error.detail); }
  }

  if (loading || !server) return <div className="detail-loading">正在加载服务器…</div>;
  const running = Boolean(status?.running);
  return <section className="detail-shell">
    <header className="detail-header">
      <button className="detail-back" onClick={() => navigate("/servers")} aria-label="返回">←</button>
      <div className="detail-title"><div className="detail-title-line"><h1>{server.name}</h1><span className={`state-pill ${running ? "running" : ""}`}>{running ? "运行中" : "已停止"}</span></div><p>{server.server_type} · Java {server.java_version} · {server.max_memory} MB{status?.pid ? ` · PID ${status.pid}` : ""}</p></div>
      <div className="detail-actions">{running ? <><button className="btn-ghost" onClick={() => action("stop")}>停止</button><button className="btn-danger" onClick={() => action("kill")}>强制终止</button></> : <button className="btn-success" onClick={() => action("start")}>启动服务器</button>}<button className="btn-ghost danger-text" onClick={remove}>删除</button></div>
    </header>
    <nav className="detail-tabs">{TABS.map((item) => <button key={item.key} className={tab === item.key ? "active" : ""} onClick={() => setTab(item.key)}>{item.label}</button>)}</nav>
    <div className="detail-workspace">
      <div hidden={tab !== "terminal"} className="detail-view"><Terminal serverUuid={uuid!} running={status?.running} /></div>
      <div hidden={tab !== "files"} className="detail-view"><FileBrowser serverUuid={uuid!} /></div>
      <div hidden={tab !== "config"} className="detail-view"><ConfigEditor serverUuid={uuid!} /></div>
      <div hidden={tab !== "backups"} className="detail-view"><BackupPanel serverUuid={uuid!} /></div>
    </div>
  </section>;
}
