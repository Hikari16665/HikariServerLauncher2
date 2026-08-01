import { NavLink, Outlet } from "react-router-dom";
import TitleBar from "./TitleBar";
import TaskFloating from "./TaskFloating";

const navigation = [
  ["/", "概览", "overview"],
  ["/servers", "服务器", "servers"],
  ["/install", "安装服务器", "install"],
  ["/import", "导入服务器", "import"],
  ["/market", "市场", "market"],
  ["/addons", "附加管理", "addons"],
  ["/diagnostics", "服务器检测", "diagnostics"],
  ["/settings", "设置", "settings"],
  ["/about", "关于", "about"],
] as const;

export default function Layout() {
  return <div className="app-shell">
    <TitleBar />
    <div className="app-frame">
      <aside className="app-nav">
        <div className="brand-block"><img src="/HSL.png" alt="HSL" /><div><strong>HSL2</strong><span>2.0.0</span></div></div>
        <nav className="nav-list">
          {navigation.map(([to, label, icon]) => <NavLink end={to === "/"} key={to} to={to} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}><NavIcon name={icon} /><span>{label}</span></NavLink>)}
        </nav>
        <div className="nav-footer"><span className="connection-dot" />后端已连接</div>
      </aside>
      <main className="app-content"><Outlet /></main>
    </div>
    <TaskFloating />
  </div>;
}

function NavIcon({ name }: { name: string }) {
  const paths: Record<string, React.ReactNode> = {
    overview: <><path d="M4 12h6V4H4zM14 20h6v-8h-6zM4 20h6v-4H4zM14 8h6V4h-6z" /></>,
    servers: <><rect x="3" y="4" width="18" height="6" rx="1"/><rect x="3" y="14" width="18" height="6" rx="1"/><path d="M7 7h.01M7 17h.01"/></>,
    install: <><path d="M12 3v12M7 10l5 5 5-5"/><path d="M4 19h16"/></>,
    import: <><path d="M5 4h9l5 5v11H5z"/><path d="M14 4v5h5M12 11v6M9 14l3 3 3-3"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1z"/></>,
    about: <><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/></>,
    market: <><path d="M4 8h16l-1 12H5zM7 8a5 5 0 0 1 10 0"/><path d="M9 12v1M15 12v1"/></>,
    addons: <><path d="M8 3h8v5h5v8h-5v5H8v-5H3V8h5z"/></>,
    diagnostics: <><path d="M12 3 4 6v5c0 5 3.4 8.4 8 10 4.6-1.6 8-5 8-10V6z"/><path d="m8.5 12 2.2 2.2 4.8-5"/></>,
  };
  return <svg viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}
