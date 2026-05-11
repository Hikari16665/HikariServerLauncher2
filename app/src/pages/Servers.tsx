import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import type { Server, ServerStatus } from "../lib/types";
import { useToastStore } from "../store/toast";
import { showConfirm } from "../components/ConfirmDialog";

export default function Servers() {
  const navigate = useNavigate();
  const [servers, setServers] = useState<Server[]>([]);
  const [statuses, setStatuses] = useState<Record<string, ServerStatus>>({});
  const [loading, setLoading] = useState(true);
  const addToast = useToastStore((s) => s.addToast);

  useEffect(() => {
    api
      .get<{ servers: Server[] }>("/api/servers")
      .then((d) => setServers(d.servers))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (servers.length === 0) return;
    const poll = () => {
      for (const s of servers) {
        api
          .get<ServerStatus>(`/api/servers/${s.uuid}/status`)
          .then((st) =>
            setStatuses((prev) => ({ ...prev, [s.uuid]: st }))
          )
          .catch(() => {});
      }
    };
    poll();
    const timer = setInterval(poll, 5000);
    return () => clearInterval(timer);
  }, [servers]);

  async function handleAction(
    uuid: string,
    action: "start" | "stop" | "kill",
    name: string
  ) {
    try {
      const data = await api.post<{ success: boolean; message?: string }>(
        `/api/servers/${uuid}/${action}`
      );
      if (data.success) {
        const st = await api.get<ServerStatus>(`/api/servers/${uuid}/status`);
        setStatuses((prev) => ({ ...prev, [uuid]: st }));
        addToast(
          `${name}: ${
            action === "start" ? "启动中" : action === "kill" ? "已强制终止" : "已停止"
          }`,
          "success"
        );
      }
    } catch (e: any) {
      addToast(e.message || `${action} failed`, "error", e.detail);
    }
  }

  async function handleDelete(uuid: string, name: string) {
    const ok = await showConfirm(
      `确认删除服务器 "${name}"？此操作不可恢复，服务器文件夹将被永久删除。`
    );
    if (!ok) return;
    try {
      await api.delete(`/api/servers/${uuid}`);
      setServers((prev) => prev.filter((s) => s.uuid !== uuid));
      setStatuses((prev) => {
        const next = { ...prev };
        delete next[uuid];
        return next;
      });
      addToast(`${name} 已删除`, "success");
    } catch (e: any) {
      addToast(e.message || "删除失败", "error", e.detail);
    }
  }

  if (loading) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          color: "var(--text-muted)",
          fontSize: 13,
        }}
      >
        加载中...
      </div>
    );
  }

  return (
    <div style={{ padding: 24, maxWidth: 800, margin: "0 auto", width: "100%", height: "100%", overflow: "auto" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 20,
        }}
      >
        <h1
          style={{
            fontSize: 20,
            fontWeight: 600,
            color: "var(--text-primary)",
          }}
        >
          服务器
        </h1>
        {servers.length > 0 && (
          <button
            className="btn-primary"
            onClick={() => navigate("/install")}
            style={{ fontSize: 13 }}
          >
            安装新服务器
          </button>
        )}
      </div>

      {servers.length === 0 ? (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "80px 0",
            color: "var(--text-muted)",
            gap: 16,
          }}
        >
          <p style={{ fontSize: 14 }}>暂无服务器</p>
          <button
            className="btn-primary"
            onClick={() => navigate("/install")}
            style={{ fontSize: 13 }}
          >
            前往安装来添加服务器
          </button>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {servers.map((s) => {
            const st = statuses[s.uuid];
            const running = st?.running;
            return (
              <div
                key={s.uuid}
                onClick={() => navigate(`/servers/${s.uuid}`)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "12px 16px",
                  background: "var(--bg-secondary)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius)",
                  cursor: "pointer",
                  transition: "border-color 0.15s, background 0.15s",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = "var(--accent)";
                  e.currentTarget.style.background = "var(--bg-tertiary)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "var(--border)";
                  e.currentTarget.style.background = "var(--bg-secondary)";
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
                  <div
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: 4,
                      background: running ? "var(--green)" : "var(--text-muted)",
                      flexShrink: 0,
                    }}
                  />
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>
                      {s.name}
                    </div>
                    <div
                      style={{
                        fontSize: 11,
                        color: "var(--text-muted)",
                        marginTop: 1,
                      }}
                    >
                      {s.server_type} / Java {s.java_version} / {s.max_memory}MB
                    </div>
                  </div>
                </div>
                <div
                  style={{ display: "flex", gap: 6, flexShrink: 0 }}
                  onClick={(e) => e.stopPropagation()}
                >
                  {running ? (
                    <>
                      <button
                        className="btn-ghost"
                        style={{ fontSize: 12, padding: "4px 10px" }}
                        onClick={() => handleAction(s.uuid, "stop", s.name)}
                      >
                        停止
                      </button>
                      <button
                        className="btn-ghost"
                        style={{ fontSize: 12, padding: "4px 10px" }}
                        onClick={() => handleAction(s.uuid, "kill", s.name)}
                      >
                        强制终止
                      </button>
                    </>
                  ) : (
                    <button
                      className="btn-success"
                      style={{ fontSize: 12, padding: "4px 10px" }}
                      onClick={() => handleAction(s.uuid, "start", s.name)}
                    >
                      启动
                    </button>
                  )}
                  <button
                    className="btn-ghost"
                    style={{ fontSize: 12, padding: "4px 10px" }}
                    onClick={() => handleDelete(s.uuid, s.name)}
                  >
                    删除
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
