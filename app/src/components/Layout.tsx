import { useState } from "react";
import { Outlet, NavLink, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import TitleBar from "./TitleBar";
import TaskFloating from "./TaskFloating";

const NAV = [
  { to: "/", label: "服务器" },
  { to: "/servers/new", label: "创建服务器" },
  { to: "/settings", label: "设置" },
];

export default function Layout() {
  const [navHover, setNavHover] = useState<string | null>(null);
  const location = useLocation();

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      {/* Custom Title Bar */}
      <TitleBar />

      {/* Top Navbar */}
      <nav
        style={{
          display: "flex",
          alignItems: "center",
          gap: 0,
          padding: "0 20px",
          height: 48,
          background: "var(--bg-secondary)",
          borderBottom: "1px solid var(--border)",
          flexShrink: 0,
        }}
      >
        {/* Logo */}
        <div
          style={{
            fontWeight: 700,
            fontSize: 16,
            color: "var(--accent)",
            marginRight: 32,
            letterSpacing: -0.5,
          }}
        >
          HSL
        </div>

        {/* Nav Links */}
        {NAV.map(({ to, label }) => {
          const active = location.pathname === to;
          return (
            <NavLink
              key={to}
              to={to}
              style={{ textDecoration: "none", position: "relative" }}
              onMouseEnter={() => setNavHover(to)}
              onMouseLeave={() => setNavHover(null)}
            >
              <div
                style={{
                  padding: "12px 16px",
                  fontSize: 13,
                  fontWeight: 500,
                  color: active
                    ? "var(--text-primary)"
                    : "var(--text-secondary)",
                  transition: "color 0.15s",
                }}
              >
                {label}
              </div>
              {(active || navHover === to) && (
                <motion.div
                  layoutId="nav-underline"
                  style={{
                    position: "absolute",
                    bottom: 0,
                    left: 8,
                    right: 8,
                    height: 2,
                    borderRadius: 1,
                    background: active ? "var(--accent)" : "var(--border)",
                  }}
                  transition={{ type: "spring", stiffness: 500, damping: 35 }}
                />
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Page Content */}
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

      {/* Task Floating Button */}
      <TaskFloating />
    </div>
  );
}
