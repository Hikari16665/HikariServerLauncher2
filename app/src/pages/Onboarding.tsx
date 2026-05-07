import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { invoke } from "@tauri-apps/api/core";
import { useSettings } from "../store/settings";
import { useToastStore } from "../store/toast";
import TitleBar from "../components/TitleBar";

const STEPS = [
  { title: "欢迎使用 HSL", desc: "Hikari Server Launcher 桌面客户端" },
  { title: "服务器地址", desc: "输入后端 API 地址" },
  { title: "管理密钥", desc: "输入管理密钥以验证身份" },
  { title: "镜像模式", desc: "选择下载源偏好" },
];

function dumpError(e: unknown): string {
  if (e === null || e === undefined) return String(e);
  if (typeof e === "string") return e;
  if (typeof e === "object") {
    try { return JSON.stringify(e, null, 2); } catch { return String(e); }
  }
  return String(e);
}

interface ProxyResponse {
  status: number;
  body: string;
  error: string | null;
}

export default function Onboarding() {
  const [step, setStep] = useState(0);
  const [apiUrl, setApiUrl] = useState("http://127.0.0.1:5000");
  const [adminKey, setAdminKey] = useState("");
  const [useMirror, setUseMirror] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState("");

  const { setApiUrl: saveUrl, setAdminKey: saveAdminKey, setAuth, setUseMirror: saveMirror, setOnboardingDone } = useSettings();
  const addToast = useToastStore((s) => s.addToast);
  const navigate = useNavigate();

  async function testAndFinish() {
    if (!adminKey.trim()) {
      setError("请输入管理密钥");
      addToast("请输入管理密钥", "error");
      return;
    }
    setTesting(true);
    setError("");

    saveUrl(apiUrl);
    saveAdminKey(adminKey);

    const url = `${apiUrl}/api/auth`;
    const detail = `POST ${url}\nAPI: ${apiUrl}\n在线: ${navigator.onLine}`;

    try {
      const resp = await invoke<ProxyResponse>("proxy_fetch", {
        req: {
          url,
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ auth_key: adminKey }),
        },
      });

      if (resp.error) {
        throw { message: resp.error, detail: `${detail}\nRust 错误: ${resp.error}` };
      }

      const data = JSON.parse(resp.body);
      if (data.success && data.token) {
        setAuth(data.token, adminKey);
        saveMirror(useMirror);
        setOnboardingDone();
        addToast("设置完成，欢迎使用 HSL", "success");
        navigate("/");
      } else {
        throw {
          message: "服务器返回异常，请检查密钥是否正确",
          detail: `${detail}\n状态: ${resp.status}\n响应: ${resp.body.slice(0, 300)}`,
        };
      }
    } catch (e: any) {
      const msg = e.message || String(e) || "无法连接到服务器";
      const full = e.detail || `${detail}\n原始错误:\n${dumpError(e)}`;
      setError(msg);
      addToast(msg, "error", full);
    } finally {
      setTesting(false);
    }
  }

  const slide = {
    enter: { x: 40, opacity: 0 },
    center: { x: 0, opacity: 1 },
    exit: { x: -40, opacity: 0 },
  };

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "var(--bg-primary)" }}>
      <TitleBar />
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ width: 420, padding: 32 }}>
          <div style={{ display: "flex", gap: 8, marginBottom: 32 }}>
            {STEPS.map((_, i) => (
              <div key={i} style={{ flex: 1, height: 3, borderRadius: 2, background: i <= step ? "var(--accent)" : "var(--border)", transition: "background 0.3s" }} />
            ))}
          </div>

          <AnimatePresence mode="wait">
            <motion.div key={step} variants={slide} initial="enter" animate="center" exit="exit" transition={{ duration: 0.25 }}>
              <h2 style={{ fontSize: 24, fontWeight: 600, marginBottom: 4, color: "var(--text-primary)" }}>{STEPS[step].title}</h2>
              <p style={{ fontSize: 14, color: "var(--text-secondary)", marginBottom: 24 }}>{STEPS[step].desc}</p>

              {step === 0 && (
                <div style={{ textAlign: "center", padding: "40px 0" }}>
                  <div style={{ fontSize: 48, fontWeight: 800, color: "var(--accent)", marginBottom: 8 }}>HSL</div>
                  <p style={{ color: "var(--text-secondary)", fontSize: 14 }}>Hikari Server Launcher</p>
                  <p style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 4 }}>轻松管理你的 Minecraft 服务器</p>
                </div>
              )}

              {step === 1 && (
                <input value={apiUrl} onChange={(e) => setApiUrl(e.target.value)} placeholder="http://127.0.0.1:5000" style={{ width: "100%", padding: "10px 12px", fontSize: 14 }} autoFocus onKeyDown={(e) => e.key === "Enter" && setStep(2)} />
              )}

              {step === 2 && (
                <div>
                  <input type="password" value={adminKey} onChange={(e) => { setAdminKey(e.target.value); setError(""); }} placeholder="输入管理密钥" style={{ width: "100%", padding: "10px 12px", fontSize: 14 }} autoFocus onKeyDown={(e) => e.key === "Enter" && testAndFinish()} />
                  {error && <motion.p initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} style={{ color: "var(--red)", fontSize: 13, marginTop: 8 }}>{error}</motion.p>}
                </div>
              )}

              {step === 3 && (
                <div onClick={() => setUseMirror(!useMirror)} style={{ display: "flex", alignItems: "center", gap: 12, padding: "16px", background: "var(--bg-secondary)", borderRadius: "var(--radius)", border: "1px solid var(--border)", cursor: "pointer" }}>
                  <div style={{ width: 44, height: 24, borderRadius: 12, background: useMirror ? "var(--accent)" : "var(--border)", position: "relative", transition: "background 0.2s", flexShrink: 0 }}>
                    <motion.div animate={{ x: useMirror ? 22 : 2 }} style={{ width: 20, height: 20, borderRadius: 10, background: "#fff", position: "absolute", top: 2 }} />
                  </div>
                  <div><div style={{ fontSize: 14, fontWeight: 500 }}>优先使用镜像源</div><div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>镜像源下载速度更快（中国大陆推荐开启）</div></div>
                </div>
              )}
            </motion.div>
          </AnimatePresence>

          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 32 }}>
            {step > 0 ? <button className="btn-ghost" onClick={() => { setStep(step - 1); setError(""); }}>上一步</button> : <div />}
            {step < 3 ? (
              <button className="btn-primary" onClick={() => setStep(step + 1)}>下一步</button>
            ) : (
              <button className="btn-primary" onClick={testAndFinish} disabled={testing}>{testing ? "正在验证..." : "完成设置"}</button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
