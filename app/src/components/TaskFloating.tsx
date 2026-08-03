import { useCallback } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useTaskStore } from "../store/tasks";
import { useWebSocket } from "../hooks/useWebSocket";
import type { TaskInfo } from "../lib/types";
import { api } from "../lib/api";
import { useToastStore } from "../store/toast";

const STATUS_LABEL: Record<string, string> = { pending: "等待中", running: "进行中", completed: "已完成", failed: "失败", cancelled: "已取消" };
function formatBytes(value?: number) { if (value === undefined) return "—"; if (value >= 1_073_741_824) return `${(value / 1_073_741_824).toFixed(1)} GB`; if (value >= 1_048_576) return `${(value / 1_048_576).toFixed(1)} MB`; return `${(value / 1024).toFixed(0)} KB`; }
function formatEta(value?: number) { if (value === undefined) return ""; return value < 60 ? `剩余 ${value} 秒` : `剩余约 ${Math.ceil(value / 60)} 分钟`; }

export default function TaskFloating() {
  const { tasks, filter, expanded, setTasks, updateTask, setFilter, setExpanded, clearCompleted } = useTaskStore();
  const addToast = useToastStore((state) => state.addToast);
  const onMessage = useCallback((raw: string) => { try { const event = JSON.parse(raw); if (event.type === "task_snapshot") setTasks(event.tasks); if (event.type === "task") updateTask(event.task as TaskInfo); } catch {} }, [setTasks, updateTask]);
  useWebSocket("/api/tasks/stream", onMessage);
  const active = tasks.filter((task) => task.status === "running" || task.status === "pending");
  const current = active[0];
  const visible = tasks.filter((task) => filter === "all" || task.status === filter);
  const completedCount = tasks.length - active.length;
  async function clearHistory() {
    try {
      const result = await api.delete<{ removed: number }>("/api/tasks/completed");
      clearCompleted();
      addToast(`已清除 ${result.removed} 条任务记录`, "success");
    } catch (error: any) {
      addToast(error.message || "无法清除任务记录", "error", error.detail);
    }
  }

  return <>
    <button className="task-statusbar" onClick={() => setExpanded(!expanded)}><span className={`status-dot ${current ? "running" : "completed"}`} /><strong>{current ? current.title || "后台任务" : "没有正在进行的任务"}</strong>{current && <><span className="task-status-message">{current.progress_message}</span><div className="task-inline-progress"><i style={{ width: `${current.progress}%` }} /></div><span>{Math.round(current.progress)}%</span></>}<span className="task-status-count">任务 {tasks.length}</span></button>
    <AnimatePresence>{expanded && <motion.aside className="task-center" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }}>
      <header><div><h2>任务</h2><p>{active.length} 个活动任务</p></div>{completedCount > 0 && <button className="btn-ghost" onClick={clearHistory}>清除已结束</button>}<button className="icon-button" aria-label="关闭任务中心" onClick={() => setExpanded(false)}>×</button></header>
      <nav className="task-filters">{(["all", "running", "pending", "completed", "failed"] as const).map((item) => <button key={item} className={filter === item ? "selected" : ""} onClick={() => setFilter(item)}>{item === "all" ? "全部" : STATUS_LABEL[item]}</button>)}</nav>
      <div className="task-list">{visible.length === 0 ? <div className="empty-state">没有相关任务</div> : visible.map((task) => <TaskRow key={task.task_id} task={task} />)}</div>
    </motion.aside>}</AnimatePresence>
  </>;
}

function TaskRow({ task }: { task: TaskInfo }) {
  const downloading = task.metrics?.downloaded_bytes !== undefined;
  return <article className={`task-card ${task.status}`}><div className="task-card-title"><span className={`status-dot ${task.status}`} /><strong>{task.title || "后台任务"}</strong><em>{STATUS_LABEL[task.status]}</em></div><p>{task.progress_message || "等待任务更新…"}</p>{(task.status === "running" || task.status === "pending") && <><div className="progress"><i style={{ width: `${task.progress}%` }} /></div><small>{Math.round(task.progress)}%</small></>}{downloading && <div className="task-metrics"><span>{formatBytes(task.metrics.downloaded_bytes)} / {formatBytes(task.metrics.total_bytes)}</span><span>{formatBytes(task.metrics.speed_bps)}/s · {formatEta(task.metrics.eta_seconds)}</span></div>}{task.steps?.length > 0 && <ol className="task-steps">{task.steps.map((step) => <li key={step.id} className={step.status}>{step.status === "completed" ? "✓" : step.status === "running" ? "›" : "·"} {step.label}</li>)}</ol>}{task.error_message && <div className="task-error">{task.error_message}</div>}</article>;
}
