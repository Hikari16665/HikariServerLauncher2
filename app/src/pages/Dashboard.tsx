import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { api, ApiError } from "../lib/api";
import type { Server, ServerStatus } from "../lib/types";
import { useToastStore } from "../store/toast";
import { showConfirm } from "../components/ConfirmDialog";

export default function Dashboard() {
  const [servers, setServers] = useState<Server[]>([]);
  const [statuses, setStatuses] = useState<Record<string, ServerStatus>>({});
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const addToast = useToastStore((s) => s.addToast);

  async function fetchServers() {
    try {
      const data = await api.get<{ servers: Server[] }>("/api/servers");
      setServers(data.servers);
    } catch (e) {
      console.error("Failed to fetch servers:", e);
    } finally {
      setLoading(false);
    }
  }

  async function fetchStatuses(serverList: Server[]) {
    const map: Record<string, ServerStatus> = {};
    await Promise.all(
      serverList.map(async (s) => {
        try {
          const st = await api.get<ServerStatus>(
            `/api/servers/${s.uuid}/status`
          );
          map[s.uuid] = st;
        } catch {
          map[s.uuid] = { running: false };
        }
      })
    );
    setStatuses(map);
  }

  useEffect(() => {
    fetchServers();
  }, []);

  useEffect(() => {
    if (servers.length === 0) return;
    fetchStatuses(servers);
    const interval = setInterval(() => fetchStatuses(servers), 5000);
    return () => clearInterval(interval);
  }, [servers.length]);

  async function handleAction(uuid: string, action: "start" | "stop" | "kill") {
    try {
      await api.post(`/api/servers/${uuid}/${action}`);
      await fetchStatuses(servers);
    } catch (e) {
      if (e instanceof ApiError) {
        addToast(e.message, "error", e.detail);
      }
    }
  }

  async function handleDelete(uuid: string, name: string) {
    if (!(await showConfirm(`确定删除服务器 "${name}"？此操作不可恢复！`))) return;
    try {
      await api.delete(`/api/servers/${uuid}`);
      addToast(`服务器 "${name}" 已删除`, "success");
      fetchServers();
    } catch (e) {
      if (e instanceof ApiError) {
        addToast(e.message, "error", e.detail);
      } else {
        addToast("删除失败", "error", String(e));
      }
    }
  }

  if (loading) {
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

  return (
    <div style={{ padding: 24, maxWidth: 900, margin: "0 auto", width: "100%" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 20,
        }}
      >
        <h1 style={{ fontSize: 20, fontWeight: 600 }}>服务器列表</h1>
      </div>

      {servers.length === 0 ? (
        <div
          style={{
            textAlign: "center",
            padding: "60px 0",
            color: "var(--text-muted)",
          }}
        >
          <p style={{ marginBottom: 16, fontSize: 14 }}>暂无服务器</p>
          <button
            className="btn-primary"
            onClick={() => navigate("/servers/new")}
          >
            创建第一个服务器
          </button>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {servers.map((s, i) => {
            const st = statuses[s.uuid];
            const running = st?.running;
            return (
              <motion.div
                key={s.uuid}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
                onClick={() => navigate(`/servers/${s.uuid}`)}
                style={{
                  padding: "16px 20px",
                  background: "var(--bg-secondary)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius)",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 16,
                  transition: "border-color 0.15s",
                }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.borderColor = "var(--accent)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.borderColor = "var(--border)")
                }
              >
                {/* Status dot */}
                <div
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: 5,
                    flexShrink: 0,
                    background: running ? "var(--green)" : "var(--text-muted)",
                    boxShadow: running
                      ? "0 0 8px var(--green)"
                      : "none",
                  }}
                />

                {/* Info */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 15,
                      fontWeight: 600,
                      color: "var(--text-primary)",
                    }}
                  >
                    {s.name}
                  </div>
                  <div
                    style={{
                      fontSize: 12,
                      color: "var(--text-muted)",
                      marginTop: 2,
                      display: "flex",
                      gap: 12,
                    }}
                  >
                    <span>{s.server_type}</span>
                    <span>{s.java_version}</span>
                    <span>{s.max_memory} MB</span>
                  </div>
                </div>

                {/* Actions */}
                <div
                  style={{ display: "flex", gap: 8 }}
                  onClick={(e) => e.stopPropagation()}
                >
                  {running ? (
                    <>
                      <button
                        className="btn-danger"
                        style={{ fontSize: 12, padding: "4px 12px" }}
                        onClick={() => handleAction(s.uuid, "stop")}
                      >
                        停止
                      </button>
                    </>
                  ) : (
                    <button
                      className="btn-success"
                      style={{ fontSize: 12, padding: "4px 12px" }}
                      onClick={() => handleAction(s.uuid, "start")}
                    >
                      启动
                    </button>
                  )}
                  <button
                    className="btn-ghost"
                    style={{ fontSize: 12, padding: "4px 8px", color: "var(--red)" }}
                    onClick={() => handleDelete(s.uuid, s.name)}
                  >
                    删除
                  </button>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
