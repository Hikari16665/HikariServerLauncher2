import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import type { Server, ServerStatus } from "../lib/types";
import { useToastStore } from "../store/toast";
import { showConfirm } from "../components/ConfirmDialog";
import Terminal from "../components/Terminal";
import FileBrowser from "../components/FileBrowser";
import ConfigEditor from "../components/ConfigEditor";
import BackupPanel from "../components/BackupPanel";

type Tab = "terminal" | "files" | "config" | "backups";

const TABS: { key: Tab; label: string }[] = [
  { key: "terminal", label: "终端" },
  { key: "files", label: "文件" },
  { key: "config", label: "配置" },
  { key: "backups", label: "备份" },
];

export default function ServerDetail() {
  const { uuid } = useParams<{ uuid: string }>();
  const navigate = useNavigate();
  const addToast = useToastStore((s) => s.addToast);
  const [server, setServer] = useState<Server | null>(null);
  const [status, setStatus] = useState<ServerStatus | null>(null);
  const [tab, setTab] = useState<Tab>("terminal");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!uuid) return;
    api
      .get<{ servers: Server[] }>("/api/servers")
      .then((d) => {
        const s = d.servers.find((x) => x.uuid === uuid);
        if (s) {
          setServer(s);
        } else {
          navigate("/");
        }
      })
      .catch(() => navigate("/"))
      .finally(() => setLoading(false));
  }, [uuid]);

  useEffect(() => {
    if (!uuid) return;
    const poll = () => {
      api
        .get<ServerStatus>(`/api/servers/${uuid}/status`)
        .then(setStatus)
        .catch(() => {});
    };
    poll();
    const interval = setInterval(poll, 3000);
    return () => clearInterval(interval);
  }, [uuid]);

  async function handleAction(action: "start" | "stop" | "kill") {
    if (!uuid) return;
    try {
      await api.post(`/api/servers/${uuid}/${action}`);
      const st = await api.get<ServerStatus>(`/api/servers/${uuid}/status`);
      setStatus(st);
    } catch (e: any) {
      addToast(e.message || "操作失败", "error", e.detail);
    }
  }

  async function handleDelete() {
    if (!uuid || !server) return;
    if (!(await showConfirm(`确定删除服务器 "${server.name}"？此操作不可恢复！`))) return;
    try {
      await api.delete(`/api/servers/${uuid}`);
      addToast(`服务器 "${server.name}" 已删除`, "success");
      navigate("/");
    } catch (e: any) {
      addToast(e.message || "删除失败", "error", e.detail);
    }
  }

  if (loading || !server) {
    return (
      <div
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--text-secondary)",
        }}
      >
        加载中...
      </div>
    );
  }

  const running = status?.running;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          padding: "12px 24px",
          borderBottom: "1px solid var(--border)",
          background: "var(--bg-secondary)",
          flexShrink: 0,
        }}
      >
        {/* Back button */}
        <button
          className="btn-ghost"
          onClick={() => navigate("/")}
          style={{ fontSize: 12, padding: "4px 8px" }}
        >
          ← 返回
        </button>

        {/* Server info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontSize: 15,
              fontWeight: 600,
              color: "var(--text-primary)",
            }}
          >
            {server.name}
          </div>
          <div
            style={{
              fontSize: 11,
              color: "var(--text-muted)",
              display: "flex",
              gap: 12,
              marginTop: 2,
            }}
          >
            <span>{server.server_type}</span>
            <span>Java {server.java_version}</span>
            <span>{server.max_memory} MB</span>
            {running && status?.pid && <span>PID {status.pid}</span>}
          </div>
        </div>

        {/* Status + Actions */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 12,
            }}
          >
            <div
              style={{
                width: 8,
                height: 8,
                borderRadius: 4,
                background: running ? "var(--green)" : "var(--text-muted)",
                boxShadow: running ? "0 0 6px var(--green)" : "none",
              }}
            />
            <span
              style={{
                color: running ? "var(--green)" : "var(--text-muted)",
                fontWeight: 500,
              }}
            >
              {running ? "运行中" : "已停止"}
            </span>
          </div>

          {running ? (
            <>
              <button
                className="btn-danger"
                style={{ fontSize: 12, padding: "4px 12px" }}
                onClick={() => handleAction("stop")}
              >
                停止
              </button>
              <button
                className="btn-ghost"
                style={{ fontSize: 12, padding: "4px 12px" }}
                onClick={() => handleAction("kill")}
              >
                强制终止
              </button>
            </>
          ) : (
            <button
              className="btn-success"
              style={{ fontSize: 12, padding: "4px 16px" }}
              onClick={() => handleAction("start")}
            >
              启动
            </button>
          )}
          <button
            className="btn-ghost"
            style={{ fontSize: 12, padding: "4px 12px", color: "var(--red)" }}
            onClick={handleDelete}
          >
            删除服务器
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: 0,
          padding: "0 24px",
          borderBottom: "1px solid var(--border)",
          background: "var(--bg-secondary)",
          flexShrink: 0,
        }}
      >
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            style={{
              padding: "8px 16px",
              fontSize: 13,
              fontWeight: 500,
              background: "transparent",
              color:
                tab === key ? "var(--text-primary)" : "var(--text-secondary)",
              borderBottom:
                tab === key
                  ? "2px solid var(--accent)"
                  : "2px solid transparent",
              borderRadius: 0,
              marginBottom: -1,
              transition: "color 0.15s, border-color 0.15s",
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab content — keep all mounted to preserve WebSocket / state */}
      <div style={{ flex: 1, overflow: "hidden" }}>
        <div style={{ display: tab === "terminal" ? undefined : "none", height: "100%" }}><Terminal serverUuid={uuid!} running={status?.running} /></div>
        <div style={{ display: tab === "files" ? undefined : "none", height: "100%" }}><FileBrowser serverUuid={uuid!} /></div>
        <div style={{ display: tab === "config" ? undefined : "none", height: "100%" }}><ConfigEditor serverUuid={uuid!} /></div>
        <div style={{ display: tab === "backups" ? undefined : "none", height: "100%" }}><BackupPanel serverUuid={uuid!} /></div>
      </div>
    </div>
  );
}
