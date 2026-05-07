import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { invoke } from "@tauri-apps/api/core";
import { useSettings } from "../store/settings";
import { useToastStore } from "../store/toast";
import TitleBar from "../components/TitleBar";

function dumpError(e: unknown): string {
  if (e === null || e === undefined) return String(e);
  if (typeof e === "string") return e;
  if (typeof e === "object") {
    try { return JSON.stringify(e, null, 2); } catch { return String(e); }
  }
  return String(e);
}

interface ProxyResponse { status: number; body: string; error: string | null; }

export default function Login() {
  const [adminKey, setAdminKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const { apiUrl, setAuth } = useSettings();
  const addToast = useToastStore((s) => s.addToast);
  const navigate = useNavigate();

  async function handleLogin() {
    if (!adminKey.trim()) { setError("请输入管理密钥"); return; }
    setLoading(true); setError("");
    const url = `${apiUrl}/api/auth`;
    const detail = `POST ${url}\nAPI: ${apiUrl}\n在线: ${navigator.onLine}`;

    try {
      const resp = await invoke<ProxyResponse>("proxy_fetch", {
        req: { url, method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ auth_key: adminKey }) },
      });
      if (resp.error) throw { message: resp.error, detail: `${detail}\nRust 错误: ${resp.error}` };
      const data = JSON.parse(resp.body);
      if (data.success && data.token) {
        setAuth(data.token, adminKey);
        addToast("验证成功", "success");
        navigate("/");
      } else {
        throw { message: "认证失败：服务器返回异常", detail: `${detail}\n状态: ${resp.status}\n响应: ${resp.body.slice(0, 300)}` };
      }
    } catch (e: any) {
      const msg = e.message || String(e) || "无法连接到服务器";
      const full = e.detail || `${detail}\n原始错误:\n${dumpError(e)}`;
      setError(msg);
      addToast(msg, "error", full);
    } finally { setLoading(false); }
  }

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "var(--bg-primary)" }}>
      <TitleBar />
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} style={{ width: 380, padding: 32 }}>
          <div style={{ fontSize: 36, fontWeight: 800, color: "var(--accent)", textAlign: "center", marginBottom: 8 }}>HSL</div>
          <p style={{ textAlign: "center", color: "var(--text-secondary)", fontSize: 14, marginBottom: 32 }}>会话已过期，请重新验证</p>
          <input type="password" value={adminKey} onChange={(e) => { setAdminKey(e.target.value); setError(""); }} placeholder="管理密钥" style={{ width: "100%", padding: "10px 12px", fontSize: 14 }} autoFocus onKeyDown={(e) => e.key === "Enter" && handleLogin()} />
          {error && <motion.p initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} style={{ color: "var(--red)", fontSize: 13, marginTop: 8 }}>{error}</motion.p>}
          <button className="btn-primary" onClick={handleLogin} disabled={loading} style={{ width: "100%", marginTop: 20, padding: "10px 0", fontSize: 14 }}>{loading ? "验证中..." : "验证"}</button>
        </motion.div>
      </div>
    </div>
  );
}
