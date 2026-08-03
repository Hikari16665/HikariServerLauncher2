import { create } from "zustand";

export interface Toast {
  id: string;
  message: string;
  detail?: string;
  type: "error" | "success" | "info";
}

interface ToastState {
  toasts: Toast[];
  addToast: (message: string, type?: Toast["type"], detail?: string) => void;
  removeToast: (id: string) => void;
}

let nextId = 0;

export const useToastStore = create<ToastState>()((set) => ({
  toasts: [],
  addToast: (message, type = "error", detail) => {
    const id = String(++nextId);
    set((s) => {
      const duplicate = s.toasts.some((toast) => toast.message === message && toast.type === type);
      return duplicate ? s : { toasts: [...s.toasts, { id, message, type, detail }] };
    });
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
    }, 8000);
  },
  removeToast: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));
