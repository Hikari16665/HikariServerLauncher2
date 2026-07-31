import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { invoke } from "@tauri-apps/api/core";
import { useSettings } from "../store/settings";
import { useToastStore } from "../store/toast";
import TitleBar from "../components/TitleBar";

interface ProxyResponse { status: number; body: string; error: string | null; }

export default function Login() {
  const [adminKey, setAdminKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const { apiUrl, setAuth } = useSettings();
  const addToast = useToastStore((state) => state.addToast);
  const navigate = useNavigate();

  async function login() {
    if (!adminKey.trim()) { setError("请输入管理员密钥"); return; }
    setLoading(true); setError("");
    try {
      const response = await invoke<ProxyResponse>("proxy_fetch", { req: { url: `${apiUrl}/api/auth`, method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ auth_key: adminKey }) } });
      if (response.error) throw new Error(response.error);
      const data = JSON.parse(response.body);
      if (!data.success || !data.token) throw new Error("管理员密钥无效");
      setAuth(data.token, adminKey); navigate("/");
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "无法连接到服务器";
      setError(message); addToast(message, "error", String(reason));
    } finally { setLoading(false); }
  }

  return <div className="standalone-shell"><TitleBar /><main className="auth-layout">
    <section className="auth-intro"><span className="page-kicker">HIKARI SERVER LAUNCHER</span><h1>管理你的<br />Minecraft 世界</h1><p>统一管理实例、控制台、文件、配置与备份。</p><dl><div><dt>连接地址</dt><dd>{apiUrl}</dd></div><div><dt>连接方式</dt><dd>本地安全会话</dd></div></dl></section>
    <motion.section className="surface auth-card" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}><img src="/HSL.png" alt="HSL" /><div><span className="section-label">WELCOME BACK</span><h2>验证管理员身份</h2><p>输入后端配置中的管理员密钥以继续。</p></div><label>管理员密钥<input type="password" value={adminKey} onChange={(event) => { setAdminKey(event.target.value); setError(""); }} placeholder="输入管理员密钥" autoFocus onKeyDown={(event) => event.key === "Enter" && login()} /></label>{error && <p className="error-banner">{error}</p>}<button className="btn-primary auth-submit" onClick={login} disabled={loading}>{loading ? "正在验证…" : "进入控制台"}</button></motion.section>
  </main></div>;
}
