import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useTaskStore } from "../store/tasks";
import { api } from "../lib/api";

export default function TaskFloating() {
  const { tasks, filter, expanded, setTasks, setFilter, setExpanded } =
    useTaskStore();

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Poll tasks
  useEffect(() => {
    const poll = async () => {
      try {
        const data = await api.get<{ tasks: any[] }>("/api/tasks");
        setTasks(data.tasks);
      } catch {}
    };
    poll();
    intervalRef.current = setInterval(poll, 2000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  const activeTasks = tasks.filter(
    (t) => t.status === "pending" || t.status === "running"
  );

  const filteredTasks = tasks.filter((t) => {
    if (filter === "all") return true;
    return t.status === filter;
  });

  const statusColor = (s: string) => {
    switch (s) {
      case "pending":
        return "var(--text-muted)";
      case "running":
        return "var(--accent)";
      case "completed":
        return "var(--green)";
      case "failed":
        return "var(--red)";
      default:
        return "var(--text-muted)";
    }
  };

  const statusLabel = (s: string) => {
    switch (s) {
      case "pending":
        return "等待中";
      case "running":
        return "执行中";
      case "completed":
        return "已完成";
      case "failed":
        return "失败";
      case "cancelled":
        return "已取消";
      default:
        return s;
    }
  };

  return (
    <>
      {/* Floating button */}
      <AnimatePresence>
        {!expanded && (
          <motion.button
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            onClick={() => setExpanded(true)}
            style={{
              position: "fixed",
              bottom: 24,
              right: 24,
              width: 48,
              height: 48,
              borderRadius: 24,
              background: activeTasks.length > 0 ? "var(--accent)" : "var(--bg-tertiary)",
              color: activeTasks.length > 0 ? "#fff" : "var(--text-secondary)",
              boxShadow: "var(--shadow)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 14,
              fontWeight: 700,
              zIndex: 100,
              border: "1px solid var(--border)",
            }}
          >
            {activeTasks.length > 0 && (
              <div
                style={{
                  position: "absolute",
                  top: -4,
                  right: -4,
                  minWidth: 18,
                  height: 18,
                  borderRadius: 9,
                  background: "var(--red)",
                  color: "#fff",
                  fontSize: 11,
                  fontWeight: 600,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  padding: "0 4px",
                }}
              >
                {activeTasks.length}
              </div>
            )}
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 20V10M18 20V4M6 20v-4" />
            </svg>
          </motion.button>
        )}
      </AnimatePresence>

      {/* Floating panel */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, y: 40, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 40, scale: 0.95 }}
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
            style={{
              position: "fixed",
              bottom: 24,
              right: 24,
              width: 400,
              maxHeight: 480,
              background: "var(--bg-secondary)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
              boxShadow: "var(--shadow)",
              zIndex: 101,
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}
          >
            {/* Header */}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "12px 16px",
                borderBottom: "1px solid var(--border)",
                flexShrink: 0,
              }}
            >
              <span style={{ fontSize: 14, fontWeight: 600 }}>任务</span>
              <button
                onClick={() => setExpanded(false)}
                className="btn-ghost"
                style={{
                  fontSize: 12,
                  padding: "2px 8px",
                  width: 24,
                  height: 24,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                ✕
              </button>
            </div>

            {/* Filter chips */}
            <div
              style={{
                display: "flex",
                gap: 6,
                padding: "8px 16px",
                borderBottom: "1px solid var(--border)",
                flexShrink: 0,
              }}
            >
              {(
                ["all", "pending", "running", "completed", "failed"] as const
              ).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  style={{
                    fontSize: 11,
                    padding: "3px 10px",
                    borderRadius: 10,
                    fontWeight: 500,
                    background:
                      filter === f ? "var(--accent)" : "var(--bg-tertiary)",
                    color:
                      filter === f
                        ? "#fff"
                        : "var(--text-secondary)",
                    border:
                      filter === f
                        ? "1px solid var(--accent)"
                        : "1px solid var(--border)",
                  }}
                >
                  {f === "all" ? "全部" : statusLabel(f)}
                </button>
              ))}
            </div>

            {/* Task list */}
            <div
              style={{
                flex: 1,
                overflow: "auto",
                padding: "8px 12px",
              }}
            >
              {filteredTasks.length === 0 ? (
                <div
                  style={{
                    textAlign: "center",
                    padding: "32px 0",
                    color: "var(--text-muted)",
                    fontSize: 13,
                  }}
                >
                  暂无任务
                </div>
              ) : (
                filteredTasks.map((task) => (
                  <div
                    key={task.task_id}
                    style={{
                      padding: "10px 12px",
                      marginBottom: 6,
                      background: "var(--bg-primary)",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--border)",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: 4,
                      }}
                    >
                      <span
                        style={{
                          fontSize: 12,
                          fontWeight: 600,
                          color: "var(--text-primary)",
                        }}
                      >
                        {task.task_id.slice(0, 8)}...
                      </span>
                      <span
                        style={{
                          fontSize: 11,
                          fontWeight: 500,
                          color: statusColor(task.status),
                        }}
                      >
                        {statusLabel(task.status)}
                      </span>
                    </div>

                    {/* Progress bar */}
                    {(task.status === "pending" ||
                      task.status === "running") && (
                      <div
                        style={{
                          height: 3,
                          borderRadius: 2,
                          background: "var(--bg-tertiary)",
                          overflow: "hidden",
                          marginBottom: 4,
                        }}
                      >
                        <motion.div
                          animate={{
                            width: `${Math.max(task.progress * 100, 2)}%`,
                          }}
                          style={{
                            height: "100%",
                            background:
                              task.status === "running"
                                ? "var(--accent)"
                                : "var(--text-muted)",
                            borderRadius: 2,
                          }}
                          transition={{ duration: 0.3 }}
                        />
                      </div>
                    )}

                    {task.progress_message && (
                      <p
                        style={{
                          fontSize: 11,
                          color: "var(--text-muted)",
                          marginTop: 2,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {task.progress_message}
                      </p>
                    )}

                    {task.error_message && (
                      <p
                        style={{
                          fontSize: 11,
                          color: "var(--red)",
                          marginTop: 4,
                          wordBreak: "break-all",
                        }}
                      >
                        {task.error_message}
                      </p>
                    )}
                  </div>
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
