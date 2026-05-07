import { motion, AnimatePresence } from "framer-motion";

interface ConfirmState {
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}

let confirmCallback: ((state: ConfirmState | null) => void) | null = null;

export function showConfirm(message: string): Promise<boolean> {
  return new Promise((resolve) => {
    confirmCallback?.({
      message,
      onConfirm: () => {
        confirmCallback?.(null);
        resolve(true);
      },
      onCancel: () => {
        confirmCallback?.(null);
        resolve(false);
      },
    });
  });
}

import { useState, useEffect } from "react";

export default function ConfirmDialog() {
  const [state, setState] = useState<ConfirmState | null>(null);

  useEffect(() => {
    confirmCallback = setState;
    return () => { confirmCallback = null; };
  }, []);

  return (
    <AnimatePresence>
      {state && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 10000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(0,0,0,0.4)",
          }}
          onClick={state.onCancel}
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "var(--bg-primary)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
              padding: 24,
              maxWidth: 400,
              width: "90%",
              boxShadow: "var(--shadow-lg)",
            }}
          >
            <p style={{
              fontSize: 14,
              color: "var(--text-primary)",
              marginBottom: 20,
              lineHeight: 1.6,
            }}>
              {state.message}
            </p>
            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
              <button
                className="btn-ghost"
                onClick={state.onCancel}
                style={{ fontSize: 13 }}
              >
                取消
              </button>
              <button
                className="btn-danger"
                onClick={state.onConfirm}
                style={{ fontSize: 13 }}
              >
                确认
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
