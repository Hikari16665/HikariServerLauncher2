import { Outlet, NavLink, useLocation } from "react-router-dom";
import TitleBar from "./TitleBar";
import TaskFloating from "./TaskFloating";

const NAV = [
  { to: "/", label: "面板" },
  { to: "/servers", label: "服务器" },
  { to: "/install", label: "安装" },
  { to: "/settings", label: "设置" },
  { to: "/about", label: "关于" },
];

export default function Layout() {
  const location = useLocation();

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      <TitleBar />

      <nav
        style={{
          display: "flex",
          alignItems: "center",
          gap: 2,
          padding: "0 16px",
          height: 44,
          background: "var(--bg-secondary)",
          borderBottom: "1px solid var(--border)",
          flexShrink: 0,
        }}
      >
        <div
          style={{
            fontWeight: 700,
            fontSize: 15,
            color: "var(--accent)",
            marginRight: 28,
            letterSpacing: "-0.03em",
            fontFamily: "var(--mono)",
          }}
        >
          HSL
        </div>

        {NAV.map(({ to, label }) => {
          const active = location.pathname === to;
          return (
            <NavLink
              key={to}
              to={to}
              style={{
                textDecoration: "none",
                padding: "6px 14px",
                fontSize: 13,
                fontWeight: active ? 600 : 500,
                color: active ? "var(--text-primary)" : "var(--text-secondary)",
                borderRadius: "var(--radius-sm)",
                background: active ? "var(--bg-tertiary)" : "transparent",
                transition: "background 0.15s, color 0.15s",
              }}
            >
              {label}
            </NavLink>
          );
        })}
      </nav>

      <main
        style={{
          flex: 1,
          overflow: "auto",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <Outlet />
      </main>

      <TaskFloating />
    </div>
  );
}
