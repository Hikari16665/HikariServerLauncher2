import { create } from "zustand";
import type { TaskInfo } from "../lib/types";

interface TaskState {
  tasks: TaskInfo[];
  filter: "all" | "pending" | "running" | "completed" | "failed";
  expanded: boolean;
  setTasks: (tasks: TaskInfo[]) => void;
  updateTask: (task: TaskInfo) => void;
  setFilter: (f: TaskState["filter"]) => void;
  setExpanded: (v: boolean) => void;
}

export const useTaskStore = create<TaskState>()((set) => ({
  tasks: [],
  filter: "running",
  expanded: false,
  setTasks: (tasks) => set({ tasks }),
  updateTask: (task) =>
    set((s) => ({
      tasks: s.tasks.map((t) => (t.task_id === task.task_id ? task : t)),
    })),
  setFilter: (filter) => set({ filter }),
  setExpanded: (expanded) => set({ expanded }),
}));
