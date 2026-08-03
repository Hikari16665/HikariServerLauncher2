import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { invoke } from "@tauri-apps/api/core";
import { useSettings } from "../store/settings";
import { useToastStore } from "../store/toast";
import TitleBar from "../components/TitleBar";

const STEPS = [{ title: "欢迎", description: "了解 HSL" }, { title: "连接", description: "配置后端地址" }, { title: "验证", description: "输入管理员密钥" }, { title: "下载", description: "选择下载来源" }];
interface ProxyResponse { status: number; body: string; error: string | null; }

export default function Onboarding() {
  const [step, setStep] = useState(0);
  const [apiUrl, setApiUrl] = useState("http://127.0.0.1:5000");
  const [adminKey, setAdminKey] = useState("");
  const [useMirror, setUseMirror] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState("");
  const settings = useSettings();
  const addToast = useToastStore((state) => state.addToast);
  const navigate = useNavigate();

  function nextStep() {
    if (step === 1) {
      try {
        const parsed = new URL(apiUrl);
        if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error();
      } catch {
        setError("请输入有效的 HTTP 或 HTTPS 后端地址");
        return;
      }
    }
    if (step === 2 && !adminKey.trim()) {
      setError("请输入管理员密钥");
      return;
    }
    setError("");
    setStep(step + 1);
  }

  async function finish() {
    if (!adminKey.trim()) { setError("请输入管理员密钥"); setStep(2); return; }
    setTesting(true); setError("");
    try {
      const response = await invoke<ProxyResponse>("proxy_fetch", { req: { url: `${apiUrl}/api/auth`, method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ auth_key: adminKey }) } });
      if (response.error) throw new Error(response.error);
      const data = JSON.parse(response.body);
      if (!data.success || !data.token) throw new Error("管理员密钥无效");
      settings.setApiUrl(apiUrl); settings.setAuth(data.token, adminKey); settings.setUseMirror(useMirror); settings.setOnboardingDone();
      navigate("/");
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "无法连接到服务器";
      setError(message); addToast(message, "error", String(reason));
    } finally { setTesting(false); }
  }

  return <div className="standalone-shell"><TitleBar /><main className="setup-layout">
    <aside className="setup-steps"><div className="setup-brand"><img src="/HSL.png" alt="HSL" /><div><strong>HSL</strong><span>首次设置</span></div></div><ol>{STEPS.map((item, index) => <li key={item.title} className={`${index === step ? "active" : ""} ${index < step ? "done" : ""}`}><i>{index < step ? "✓" : index + 1}</i><div><strong>{item.title}</strong><span>{item.description}</span></div></li>)}</ol></aside>
    <section className="setup-workspace"><div className="setup-progress"><i style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} /></div><AnimatePresence mode="wait"><motion.div className="surface setup-card" key={step} initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }}>
      <div className="setup-card-head"><span className="page-kicker">STEP {step + 1} OF {STEPS.length}</span><h1>{step === 0 ? "欢迎使用 HSL" : step === 1 ? "连接后端服务" : step === 2 ? "验证管理员身份" : "选择下载来源"}</h1><p>{step === 0 ? "几步设置后即可开始管理 Minecraft 服务端。" : step === 1 ? "输入 HSL 后端正在监听的 API 地址。" : step === 2 ? "密钥仅用于换取本地会话令牌。" : "中国大陆网络环境通常适合启用镜像。"}</p></div>
      <div className="setup-card-body">{step === 0 && <div className="setup-feature-grid"><div><b>多实例</b><span>集中管理不同服务端</span></div><div><b>实时终端</b><span>WebSocket 控制台</span></div><div><b>文件与备份</b><span>日常维护集中完成</span></div></div>}{step === 1 && <label>API 地址<input value={apiUrl} onChange={(event) => setApiUrl(event.target.value)} placeholder="http://127.0.0.1:5000" autoFocus /></label>}{step === 2 && <label>管理员密钥<input type="password" value={adminKey} onChange={(event) => { setAdminKey(event.target.value); setError(""); }} placeholder="输入管理员密钥" autoFocus /></label>}{step === 3 && <button className={`source-option ${useMirror ? "active" : ""}`} onClick={() => setUseMirror(!useMirror)}><div><strong>优先使用镜像源</strong><span>改善部分网络环境下的 Java 和服务端下载速度</span></div><span>{useMirror ? "已启用" : "未启用"}</span></button>}{error && <p className="error-banner">{error}</p>}</div>
      <footer className="setup-actions">{step > 0 ? <button className="btn-ghost" onClick={() => { setError(""); setStep(step - 1); }}>上一步</button> : <span />}{step < STEPS.length - 1 ? <button className="btn-primary" onClick={nextStep} disabled={(step === 1 && !apiUrl.trim()) || (step === 2 && !adminKey.trim())}>下一步</button> : <button className="btn-primary" onClick={finish} disabled={testing}>{testing ? "正在验证…" : "完成设置"}</button>}</footer>
    </motion.div></AnimatePresence></section>
  </main></div>;
}
