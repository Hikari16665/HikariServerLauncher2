import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { useSettings } from "../store/settings";
import { api } from "../lib/api";
import { THEMES, applyTheme } from "../lib/themes";

export default function Settings() {
  const {
    apiUrl,
    adminKey,
    useMirror,
    theme,
    setApiUrl,
    setAdminKey,
    setAuth,
    setUseMirror,
    setTheme,
  } = useSettings();

  const [url, setUrl] = useState(apiUrl);
  const [key, setKey] = useState(adminKey);
  const [mirror, setMirror] = useState(useMirror);
  const [saved, setSaved] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<"success" | "fail" | null>(null);

  useEffect(() => {
    setUrl(apiUrl);
    setKey(adminKey);
    setMirror(useMirror);
  }, [apiUrl, adminKey, useMirror]);

  async function handleSave() {
    setApiUrl(url);
    setAdminKey(key);
    setUseMirror(mirror);

    if (key) {
      try {
        const resp = await fetch(`${url}/api/auth`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ auth_key: key }),
        });
        const data = await resp.json();
        if (data.success && data.token) {
          setAuth(data.token, key);
        }
      } catch {
        // keep old token, will auto-reconnect
      }
    }

    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  async function testConnection() {
    setTesting(true);
    setTestResult(null);
    try {
      const resp = await api.get<{ success: boolean }>("/api/ping");
      setTestResult(resp.success ? "success" : "fail");
    } catch {
      setTestResult("fail");
    } finally {
      setTesting(false);
    }
  }

  const sectionStyle: React.CSSProperties = {
    marginBottom: 22,
  };

  const labelStyle: React.CSSProperties = {
    fontSize: 12,
    fontWeight: 600,
    color: "var(--text-secondary)",
    display: "block",
    marginBottom: 5,
  };

  return (
    <div style={{ padding: 24, maxWidth: 600, margin: "0 auto", width: "100%", height: "100%", overflow: "auto" }}>
      <h1 style={{ fontSize: 20, fontWeight: 600, color: "var(--text-primary)", marginBottom: 24 }}>
        设置
      </h1>

        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {/* API URL */}
          <div style={sectionStyle}>
            <label style={labelStyle}>API 地址</label>
            <div style={{ display: "flex", gap: 8 }}>
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                style={{ flex: 1 }}
              />
              <button
                className="btn-ghost"
                onClick={testConnection}
                disabled={testing}
                style={{ fontSize: 12, whiteSpace: "nowrap" }}
              >
                {testing ? "测试中..." : "测试连接"}
              </button>
            </div>
            {testResult && (
              <motion.p
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                style={{
                  fontSize: 12,
                  marginTop: 6,
                  color:
                    testResult === "success" ? "var(--green)" : "var(--red)",
                }}
              >
                {testResult === "success" ? "连接成功" : "连接失败"}
              </motion.p>
            )}
          </div>

          {/* Admin Key */}
          <div style={sectionStyle}>
            <label style={labelStyle}>管理密钥</label>
            <input
              type="password"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              style={{ width: "100%" }}
              placeholder="输入管理密钥"
            />
          </div>

          {/* Mirror mode */}
          <div style={sectionStyle}>
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "14px 16px",
                background: "var(--bg-secondary)",
                borderRadius: "var(--radius)",
                border: "1px solid var(--border)",
                cursor: "pointer",
              }}
            >
              <div
                onClick={() => setMirror(!mirror)}
                style={{
                  width: 44,
                  height: 24,
                  borderRadius: 12,
                  background: mirror ? "var(--accent)" : "var(--border)",
                  position: "relative",
                  transition: "background 0.2s",
                  flexShrink: 0,
                }}
              >
                <motion.div
                  animate={{ x: mirror ? 22 : 2 }}
                  style={{
                    width: 20,
                    height: 20,
                    borderRadius: 10,
                    background: "#fff",
                    position: "absolute",
                    top: 2,
                  }}
                />
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 500 }}>
                  优先使用镜像源
                </div>
                <div
                  style={{
                    fontSize: 12,
                    color: "var(--text-muted)",
                    marginTop: 2,
                  }}
                >
                  镜像源下载速度更快（中国大陆推荐开启）
                </div>
              </div>
            </label>
          </div>

          {/* Theme Selector */}
          <div style={sectionStyle}>
            <label style={labelStyle}>配色方案</label>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6, marginTop: 2 }}>
              {THEMES.map((t) => (
                <button
                  key={t.name}
                  onClick={() => {
                    setTheme(t.name);
                    applyTheme(t.name);
                  }}
                  style={{
                    padding: "8px 6px",
                    fontSize: 12,
                    fontWeight: 500,
                    borderRadius: "var(--radius-sm)",
                    border: theme === t.name ? "2px solid var(--accent)" : "1px solid var(--border)",
                    background: theme === t.name ? "var(--accent-light)" : "var(--bg-secondary)",
                    color: theme === t.name ? "var(--accent)" : "var(--text-secondary)",
                    cursor: "pointer",
                    transition: "all 0.15s",
                  }}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* Save */}
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button className="btn-primary" onClick={handleSave}>
              保存设置
            </button>
            {saved && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                style={{ fontSize: 13, color: "var(--green)" }}
              >
                已保存
              </motion.span>
            )}
          </div>
        </div>
    </div>
  );
}
