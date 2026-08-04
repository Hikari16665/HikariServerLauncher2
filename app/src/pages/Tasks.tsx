import { useCallback } from "react";
import { useTaskStore } from "../store/tasks";
import { useWebSocket } from "../hooks/useWebSocket";
import type { TaskInfo } from "../lib/types";
import { api } from "../lib/api";
import { useToastStore } from "../store/toast";

const labels: Record<string, string> = { pending: "等待中", running: "进行中", completed: "已完成", failed: "失败", cancelled: "已取消" };
const bytes = (value?: number) => value === undefined ? "—" : value >= 1_048_576 ? `${(value / 1_048_576).toFixed(1)} MB` : `${Math.round(value / 1024)} KB`;

export default function Tasks() {
  const { tasks, filter, setTasks, updateTask, setFilter, clearCompleted } = useTaskStore();
  const toast = useToastStore((state) => state.addToast);
  const onMessage = useCallback((raw: string) => { try { const event = JSON.parse(raw); if (event.type === "task_snapshot") setTasks(event.tasks); if (event.type === "task") updateTask(event.task); } catch {} }, [setTasks, updateTask]);
  useWebSocket("/api/tasks/stream", onMessage);
  const active = tasks.filter((task) => task.status === "running" || task.status === "pending");
  const visible = tasks.filter((task) => filter === "all" || task.status === filter);
  const clear = async () => { try { const result = await api.delete<{ removed: number }>("/api/tasks/completed"); clearCompleted(); toast(`已清除 ${result.removed} 条记录`, "success"); } catch (error: any) { toast(error.message || "清除失败", "error", error.detail); } };
  return <section className="page-shell tasks-page"><header className="utility-header"><div><h1>任务</h1><p>{active.length} 个进行中 · {tasks.length} 条记录</p></div><button className="btn-ghost" onClick={clear} disabled={tasks.length === active.length}>清除已结束</button></header><nav className="task-filters">{(["all", "running", "pending", "completed", "failed"] as const).map((item) => <button key={item} className={filter === item ? "selected" : ""} onClick={() => setFilter(item)}>{item === "all" ? "全部" : labels[item]}</button>)}</nav><div className="workspace-task-list">{visible.length === 0 ? <div className="empty-state">没有相关任务</div> : visible.map((task: TaskInfo) => <article className={`task-card ${task.status}`} key={task.task_id}><div className="task-card-title"><span className={`status-dot ${task.status}`}/><strong>{task.title || "后台任务"}</strong><em>{labels[task.status]}</em></div><p>{task.progress_message || "等待任务更新"}</p>{(task.status === "running" || task.status === "pending") && <><div className="progress"><i style={{ width: `${task.progress}%` }}/></div><small>{Math.round(task.progress)}%</small></>}{task.metrics?.downloaded_bytes !== undefined && <div className="task-metrics"><span>{bytes(task.metrics.downloaded_bytes)} / {bytes(task.metrics.total_bytes)}</span><span>{bytes(task.metrics.speed_bps)}/s</span></div>}{task.steps?.length > 0 && <ol className="task-steps">{task.steps.map((step) => <li key={step.id} className={step.status}>{step.label}</li>)}</ol>}{task.error_message && <div className="task-error">{task.error_message}</div>}</article>)}</div></section>;
}
