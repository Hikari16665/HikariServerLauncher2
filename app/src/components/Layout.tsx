import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import TitleBar from "./TitleBar";
import { api } from "../lib/api";

export default function Layout() {
  const [connected, setConnected] = useState<boolean | null>(null);
  useEffect(() => {
    let active = true;
    const check = () => api.get<{ valid: boolean }>("/api/auth/verify").then((result) => { if (active) setConnected(result.valid); }).catch(() => { if (active) setConnected(false); });
    check();
    const timer = window.setInterval(check, 10000);
    return () => { active = false; clearInterval(timer); };
  }, []);
  return <div className="home-window"><TitleBar/><header className="home-command"><div className="home-brand"><img src="/HSL.png" alt="HSL2"/><div><strong>HSL2</strong><span>工作区主页</span></div></div><div className={`home-connection ${connected ? "connected" : connected === false ? "offline" : "checking"}`}><i/>{connected ? "后端已连接" : connected === false ? "连接中断" : "正在检查"}</div></header><main className="home-content"><Outlet/></main></div>;
}
