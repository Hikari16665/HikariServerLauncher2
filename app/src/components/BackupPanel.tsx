import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api } from "../lib/api";
import type { BackupInfo, TaskInfo } from "../lib/types";
import { useToastStore } from "../store/toast";
import { showConfirm } from "./ConfirmDialog";

interface Props {
  serverUuid: string;
}

export default function BackupPanel({ serverUuid }: Props) {
  const [backups, setBackups] = useState<BackupInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [restoring, setRestoring] = useState<string | null>(null);
  const addToast = useToastStore((s) => s.addToast);

  async function fetchBackups() {
    try {
      const data = await api.get<{ backups: BackupInfo[] }>(
        `/api/servers/${serverUuid}/backups`
      );
      setBackups(data.backups);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchBackups();
  }, [serverUuid]);

  async function handleCreate() {
    setCreating(true);
    try {
      const resp = await api.post<{ task_id: string }>(`/api/servers/${serverUuid}/backups`);
      addToast("备份任务已创建", "info");
      // Poll task until complete, then refresh
      let attempts = 0;
      while (attempts < 120) {
        await new Promise((r) => setTimeout(r, 1000));
        try {
          const task = await api.get<TaskInfo>(`/api/tasks/${resp.task_id}`);
          if (task.status === "completed") {
            await fetchBackups();
            addToast("备份完成", "success");
            break;
          }
          if (task.status === "failed") {
            addToast(task.error_message || "备份失败", "error");
            break;
          }
        } catch { break; }
        attempts++;
      }
    } catch (e: any) {
      addToast(e.message || "创建备份失败", "error", e.detail);
    } finally {
      setCreating(false);
    }
  }

  async function handleRestore(filename: string) {
    if (!(await showConfirm(`确定从备份 ${filename} 恢复？当前文件将被覆盖。`))) return;
    setRestoring(filename);
    try {
      const resp = await api.post<{ task_id: string }>(
        `/api/servers/${serverUuid}/backups/${encodeURIComponent(filename)}/restore`
      );
      addToast("恢复任务已创建", "info");
      let attempts = 0;
      while (attempts < 120) {
        await new Promise((r) => setTimeout(r, 1000));
        try {
          const task = await api.get<TaskInfo>(`/api/tasks/${resp.task_id}`);
          if (task.status === "completed") {
            addToast("备份恢复成功", "success");
            break;
          }
          if (task.status === "failed") {
            addToast(task.error_message || "恢复失败", "error");
            break;
          }
        } catch { break; }
        attempts++;
      }
    } catch (e: any) {
      addToast(e.message || "恢复失败", "error", e.detail);
    } finally {
      setRestoring(null);
    }
  }

  async function handleDelete(filename: string) {
    if (!(await showConfirm(`确定删除备份 ${filename}？`))) return;
    try {
      await api.delete(
        `/api/servers/${serverUuid}/backups/${encodeURIComponent(filename)}`
      );
      await fetchBackups();
      addToast("备份已删除", "success");
    } catch (e: any) {
      addToast(e.message || "删除失败", "error", e.detail);
    }
  }

  return (
    <div style={{ height: "100%", overflow: "auto", padding: 16 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
        <h3
          style={{
            fontSize: 14,
            fontWeight: 600,
            color: "var(--text-primary)",
          }}
        >
          备份管理
        </h3>
        <button
          className="btn-primary"
          onClick={handleCreate}
          disabled={creating}
          style={{ fontSize: 12 }}
        >
          {creating ? "创建中..." : "创建备份"}
        </button>
      </div>

      {loading ? (
        <div
          style={{
            textAlign: "center",
            padding: 32,
            color: "var(--text-muted)",
            fontSize: 13,
          }}
        >
          加载中...
        </div>
      ) : backups.length === 0 ? (
        <div
          style={{
            textAlign: "center",
            padding: "40px 0",
            color: "var(--text-muted)",
            fontSize: 13,
          }}
        >
          暂无备份
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {backups
            .slice()
            .sort(
              (a, b) =>
                new Date(b.created).getTime() - new Date(a.created).getTime()
            )
            .map((b, i) => (
              <motion.div
                key={b.filename}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.03 }}
                style={{
                  padding: "12px 16px",
                  background: "var(--bg-secondary)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-sm)",
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: 500,
                      color: "var(--text-primary)",
                    }}
                  >
                    {b.filename}
                  </div>
                  <div
                    style={{
                      fontSize: 11,
                      color: "var(--text-muted)",
                      marginTop: 2,
                      display: "flex",
                      gap: 12,
                    }}
                  >
                    <span>{formatSize(b.size)}</span>
                    <span>
                      {new Date(b.created).toLocaleString("zh-CN")}
                    </span>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  <button
                    className="btn-ghost"
                    style={{ fontSize: 11, padding: "4px 10px" }}
                    onClick={() => handleRestore(b.filename)}
                    disabled={restoring === b.filename}
                  >
                    {restoring === b.filename ? "恢复中..." : "恢复"}
                  </button>
                  <button
                    className="btn-ghost"
                    style={{
                      fontSize: 11,
                      padding: "4px 10px",
                      color: "var(--red)",
                    }}
                    onClick={() => handleDelete(b.filename)}
                  >
                    删除
                  </button>
                </div>
              </motion.div>
            ))}
        </div>
      )}
    </div>
  );
}

function formatSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1
  );
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}
