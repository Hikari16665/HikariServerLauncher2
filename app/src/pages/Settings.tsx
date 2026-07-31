import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useSettings } from "../store/settings";
import { api } from "../lib/api";
import { THEMES, applyTheme } from "../lib/themes";

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
    try { await api.get("/api/auth/verify"); setTestResult("success"); } catch { setTestResult("fail"); } finally { setTesting(false); }
  }

  return <section className="page-shell">
    <header className="page-header"><div><span className="page-kicker">PREFERENCES</span><h1>设置</h1><p>管理连接、下载来源和界面主题。</p></div><div className="header-actions"><button className="btn-primary" onClick={save}>保存更改</button>{saved && <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="success-text">已保存</motion.span>}</div></header>
    <div className="page-body settings-layout">
      <article className="surface settings-card"><div className="settings-card-head"><div><span className="section-label">CONNECTION</span><h2>后端连接</h2><p>桌面客户端连接 HSL 后端所使用的地址和凭据。</p></div></div><div className="form-stack"><label>API 地址<div className="input-action"><input value={url} onChange={(event) => setUrl(event.target.value)} /><button className="btn-ghost" onClick={testConnection} disabled={testing}>{testing ? "测试中…" : "测试"}</button></div>{testResult && <small className={testResult === "success" ? "success-text" : "error-text"}>{testResult === "success" ? "连接成功" : "连接失败"}</small>}</label><label>管理员密钥<input type="password" value={key} onChange={(event) => setKey(event.target.value)} placeholder="输入管理员密钥" /></label></div></article>
      <article className="surface settings-card"><div className="settings-card-head"><div><span className="section-label">DOWNLOADS</span><h2>下载来源</h2><p>根据当前网络环境选择是否优先使用镜像。</p></div><button className={`switch ${mirror ? "active" : ""}`} onClick={() => setMirror(!mirror)} aria-label="切换镜像"><i /></button></div><div className="setting-note">{mirror ? "已优先使用镜像源" : "当前使用官方来源"}</div></article>
      <article className="surface settings-card settings-card-wide"><div className="settings-card-head"><div><span className="section-label">APPEARANCE</span><h2>界面主题</h2><p>颜色完全由现有主题系统控制。</p></div></div><div className="theme-grid">{THEMES.map((theme) => <button key={theme.name} className={`theme-option ${settings.theme === theme.name ? "active" : ""}`} onClick={() => { settings.setTheme(theme.name); applyTheme(theme.name); }}><span>{theme.label}</span>{settings.theme === theme.name && <b>当前</b>}</button>)}</div></article>
    </div>
  </section>;
}
