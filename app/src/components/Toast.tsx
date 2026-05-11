import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useToastStore, type Toast } from "../store/toast";

const COLORS = {
  error: { bg: "var(--red)", text: "#fff" },
  success: { bg: "var(--green)", text: "#fff" },
  info: { bg: "var(--accent)", text: "#fff" },
};

function ToastItem({ t }: { t: Toast }) {
  const [expanded, setExpanded] = useState(!!t.detail);
  const removeToast = useToastStore((s) => s.removeToast);
  const c = COLORS[t.type];
  const hasDetail = !!t.detail;

  return (
    <motion.div
      initial={{ opacity: 0, x: 60, scale: 0.95 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 60, scale: 0.95 }}
      onClick={() => {
        if (hasDetail) {
          setExpanded(!expanded);
        } else {
          removeToast(t.id);
        }
      }}
      style={{
        background: c.bg,
        color: c.text,
        borderRadius: "var(--radius-sm)",
        fontSize: 13,
        fontWeight: 500,
        cursor: "pointer",
        maxWidth: 400,
        boxShadow: "0 4px 16px rgba(0,0,0,0.3)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "10px 18px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <span style={{ wordBreak: "break-word", flex: 1 }}>{t.message}</span>
        <span style={{ fontSize: 10, opacity: 0.7, flexShrink: 0 }}>
          {hasDetail ? (expanded ? "收起" : "详情") : "✕"}
        </span>
      </div>
      <AnimatePresence>
        {expanded && t.detail && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            style={{ overflow: "hidden" }}
          >
            <div
              style={{
                padding: "0 18px 10px",
                fontSize: 11,
                opacity: 0.85,
                fontFamily: "var(--mono)",
                whiteSpace: "pre-wrap",
                wordBreak: "break-all",
                borderTop: "1px solid rgba(255,255,255,0.2)",
                paddingTop: 8,
                margin: "0 18px 10px",
              }}
            >
              {t.detail}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);

  return (
    <div
      style={{
        position: "fixed",
        top: 100,
        right: 12,
        zIndex: 9999,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        pointerEvents: "auto",
      }}
    >
      <AnimatePresence>
        {toasts.map((t) => (
          <ToastItem key={t.id} t={t} />
        ))}
      </AnimatePresence>
    </div>
  );
}
