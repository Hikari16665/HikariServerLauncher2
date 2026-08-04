import { useState, useEffect, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";

export default function TitleBar({ title = "Hikari Server Launcher", compact = false }: { title?: string; compact?: boolean }) {
  const [maximized, setMaximized] = useState(false);

  // Poll maximize state
  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const v = await invoke<boolean>("win_is_maximized");
        if (active) setMaximized(v);
      } catch {}
    };
    poll();
    const id = setInterval(poll, 500);
    return () => { active = false; clearInterval(id); };
  }, []);

  const handleMouseDown = (e: React.MouseEvent) => {
    // Only drag from the title area, not buttons
    const target = e.target as HTMLElement;
    if (target.tagName === "BUTTON" || target.closest("button")) return;
    invoke("win_start_dragging").catch(() => {});
  };

  return (
    <div
      data-tauri-drag-region
      onMouseDown={handleMouseDown}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        height: 40,
        flexShrink: 0,
        background: "var(--bg-secondary)",
        borderBottom: "1px solid var(--border)",
        paddingLeft: 14,
        zIndex: 9999,
      }}
    >
      <span style={{ fontSize: 12, fontWeight: 600, color: "var(--accent)", letterSpacing: -0.3 }}>
        {title}
      </span>

      <div style={{ display: "flex", height: "100%" }}>
        <TitleButton action="win_minimize">
          <svg width="10" height="1" viewBox="0 0 10 1"><line x1="0" y1="0.5" x2="10" y2="0.5" stroke="currentColor" strokeWidth="1.5"/></svg>
        </TitleButton>

        {!compact && <TitleButton action="win_toggle_maximize">
          {maximized ? (
            <svg width="10" height="10" viewBox="0 0 10 10">
              <rect x="2.5" y="0" width="6.5" height="6.5" fill="none" stroke="currentColor" strokeWidth="1"/>
              <rect x="0" y="3" width="6.5" height="6.5" fill="var(--bg-secondary)" stroke="currentColor" strokeWidth="1"/>
            </svg>
          ) : (
            <svg width="10" height="10" viewBox="0 0 10 10">
              <rect x="0.5" y="0.5" width="9" height="9" fill="none" stroke="currentColor" strokeWidth="1"/>
            </svg>
          )}
        </TitleButton>}

        <TitleButton action="win_close" hoverColor="#ef4444">
          <svg width="10" height="10" viewBox="0 0 10 10">
            <line x1="0" y1="0" x2="10" y2="10" stroke="currentColor" strokeWidth="1.3"/>
            <line x1="10" y1="0" x2="0" y2="10" stroke="currentColor" strokeWidth="1.3"/>
          </svg>
        </TitleButton>
      </div>
    </div>
  );
}

function TitleButton({
  action,
  children,
  hoverColor,
}: {
  action: string;
  children: React.ReactNode;
  hoverColor?: string;
}) {
  const ref = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const handler = (e: Event) => {
      e.preventDefault();
      e.stopPropagation();
      invoke(action).catch(() => {});
    };
    // Use capture phase to beat Tauri's drag interception
    el.addEventListener("click", handler, true);
    return () => el.removeEventListener("click", handler, true);
  }, [action]);

  return (
    <button
      ref={ref}
      type="button"
      tabIndex={-1}
      style={{
        width: 46,
        height: "100%",
        borderRadius: 0,
        background: "transparent",
        color: "var(--text-secondary)",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        border: "none",
        cursor: "pointer",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = hoverColor || "var(--bg-tertiary)";
        if (hoverColor) e.currentTarget.style.color = "#fff";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "transparent";
        e.currentTarget.style.color = "var(--text-secondary)";
      }}
    >
      {children}
    </button>
  );
}
