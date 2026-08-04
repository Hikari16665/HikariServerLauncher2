import { useCallback, useMemo } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useTaskStore } from "../store/tasks";
import { useWebSocket } from "../hooks/useWebSocket";
import type { TaskInfo } from "../lib/types";
import { useSettings } from "../store/settings";

function speed(value?: number) {
  if (!value) return "";
  return value >= 1_048_576 ? `${(value / 1_048_576).toFixed(1)} MB/s` : `${Math.round(value / 1024)} KB/s`;
}

export default function WorkspaceOrb() {
  const { tasks, setTasks, updateTask } = useTaskStore();
  const enabled = useSettings((state) => state.onboardingDone && Boolean(state.token));
  const onMessage = useCallback((raw: string) => { try { const event = JSON.parse(raw); if (event.type === "task_snapshot") setTasks(event.tasks); if (event.type === "task") updateTask(event.task as TaskInfo); } catch {} }, [setTasks, updateTask]);
  useWebSocket("/api/tasks/stream", onMessage, enabled);
  const active = useMemo(() => tasks.filter((task) => task.status === "running" || task.status === "pending"), [tasks]);
  const task = active[0];
  const progress = Math.max(0, Math.min(100, task?.progress || 0));
  const perimeter = 216;
  return <main className="workspace-orb-window" data-tauri-drag-region>
    {task && <button className="orb-task" onClick={(event) => { event.stopPropagation(); invoke("open_workspace_window", { label: "tasks", route: "/tasks", title: "任务" }); }}><strong>{task.title || "后台任务"}</strong><span>{task.progress_message || "等待更新"}{task.metrics?.speed_bps ? ` · ${speed(task.metrics.speed_bps)}` : ""}</span></button>}
    <div className="orb-controls"><span className="orb-grip" data-tauri-drag-region aria-label="拖动悬浮窗">⠿</span><button className="orb-core" aria-label="展开 HSL2 工作区" onClick={() => invoke("toggle_workspace_menu")} onDoubleClick={() => invoke("show_home")}>
      {task && <svg className={`orb-progress ${task.progress <= 0 ? "indeterminate" : ""}`} viewBox="0 0 64 64"><rect x="2" y="2" width="60" height="60" rx="10" pathLength={perimeter} style={{ strokeDasharray: perimeter, strokeDashoffset: perimeter * (1 - progress / 100) }}/></svg>}
      <img src="/HSL.png" alt="" />
      {active.length > 1 && <b>{active.length}</b>}
    </button></div>
  </main>;
}
