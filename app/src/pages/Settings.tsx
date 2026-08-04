import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useSettings } from "../store/settings";
import { invoke } from "@tauri-apps/api/core";
import { THEMES } from "../lib/themes";

export default function Settings() {
  const settings = useSettings();
  const [url, setUrl] = useState(settings.apiUrl);
  const [key, setKey] = useState(settings.adminKey);
  const [mirror, setMirror] = useState(settings.useMirror);
  const [saved, setSaved] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<"success" | "fail" | null>(null);
  useEffect(() => { setUrl(settings.apiUrl); setKey(settings.adminKey); setMirror(settings.useMirror); }, [settings.apiUrl, settings.adminKey, settings.useMirror]);

  async function save() {
    settings.setApiUrl(url); settings.setAdminKey(key); settings.setUseMirror(mirror);
    setSaved(true); setTimeout(() => setSaved(false), 2000);
  }
  async function testConnection() {
    setTesting(true); setTestResult(null);
    try {
      const endpoint = url.trim().replace(/\/$/, "");
      const response = await invoke<{ status: number; body: string; error: string | null }>("proxy_fetch", {
        req: { url: `${endpoint}/api/auth`, method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ auth_key: key.trim() }) },
      });
      setTestResult(!response.error && response.status >= 200 && response.status < 300 ? "success" : "fail");
    } catch { setTestResult("fail"); } finally { setTesting(false); }
  }

  return <section className="page-shell">
    <header className="page-header"><div><span className="page-kicker">PREFERENCES</span><h1>设置</h1><p>后端连接、下载来源与界面主题</p></div><div className="header-actions"><button className="btn-primary" onClick={save}>保存更改</button>{saved && <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="success-text">已保存</motion.span>}</div></header>
    <div className="page-body settings-layout">
      <article className="surface settings-card"><div className="settings-card-head"><div><span className="section-label">CONNECTION</span><h2>后端连接</h2><p>设置后端 API 地址和管理员密钥</p></div></div><div className="form-stack"><label>API 地址<div className="input-action"><input value={url} onChange={(event) => setUrl(event.target.value)} /><button className="btn-ghost" onClick={testConnection} disabled={testing}>{testing ? "测试中…" : "测试"}</button></div>{testResult && <small className={testResult === "success" ? "success-text" : "error-text"}>{testResult === "success" ? "连接成功" : "连接失败"}</small>}</label><label>管理员密钥<input type="password" value={key} onChange={(event) => setKey(event.target.value)} placeholder="输入管理员密钥" /></label></div></article>
      <article className="surface settings-card"><div className="settings-card-head"><div><span className="section-label">DOWNLOADS</span><h2>下载来源</h2><p>设置 Java 和服务端文件的下载来源</p></div><button className={`switch ${mirror ? "active" : ""}`} onClick={() => setMirror(!mirror)} aria-label="切换镜像"><i /></button></div><div className="setting-note">{mirror ? "优先使用镜像源" : "使用官方来源"}</div></article>
      <article className="surface settings-card settings-card-wide"><div className="settings-card-head"><div><span className="section-label">APPEARANCE</span><h2>界面主题</h2><p>选择界面配色</p></div></div><div className="theme-grid">{THEMES.map((theme) => <button key={theme.name} className={`theme-option ${settings.theme === theme.name ? "active" : ""}`} onClick={() => settings.setTheme(theme.name)}><span>{theme.label}</span>{settings.theme === theme.name && <b>当前</b>}</button>)}</div></article>
    </div>
  </section>;
}
