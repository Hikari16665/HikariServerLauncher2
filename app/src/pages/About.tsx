import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { openUrl } from "@tauri-apps/plugin-opener";
import { api } from "../lib/api";

function handleOpen(url: string) {
  return (e: React.MouseEvent) => {
    e.preventDefault();
    openUrl(url);
  };
}

// BUILD_HASH_PLACEHOLDER
const BUILD_HASH = "TODO";

export default function About() {
  const [licenseText, setLicenseText] = useState<string | null>(null);
  const [licenseError, setLicenseError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<{ text: string }>("/api/system/license")
      .then((d) => setLicenseText(d.text))
      .catch((e) => setLicenseError(e.message || "无法加载许可证文本"));
  }, []);


  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        padding: 24,
        maxWidth: 700,
        margin: "0 auto",
        width: "100%",
      }}
    >
      {/* Icon */}
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          marginBottom: 16,
        }}
      >
        <img
          src="/HSL.png"
          alt="HSL Icon"
          style={{ width: 72, height: 72 }}
        />
      </div>

      {/* App Name */}
      <h1
        style={{
          textAlign: "center",
          fontSize: 20,
          fontWeight: 700,
          color: "var(--text-primary)",
          marginBottom: 8,
        }}
      >
        Hikari Server Launcher 2
      </h1>

      {/* Build Hash */}
      <div
        style={{
          textAlign: "center",
          marginBottom: 20,
        }}
      >
        <span
          style={{
            fontSize: 11,
            fontFamily: "var(--mono)",
            color: "var(--text-muted)",
            background: "var(--bg-secondary)",
            padding: "4px 10px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border)",
          }}
        >
          Build: {BUILD_HASH}
        </span>
      </div>

      {/* GPLv3 Legal Notice */}
      <div
        style={{
          padding: "14px 18px",
          background: "var(--yellow-bg)",
          border: "1px solid var(--yellow)",
          borderRadius: "var(--radius)",
          marginBottom: 20,
          fontSize: 13,
          lineHeight: 1.7,
          color: "var(--text-primary)",
        }}
      >
        <strong>法律声明</strong>
        <br />
        此软件由 GNU General Public License v3.0 提供法律保证。使用本软件的行为即视为您已阅读、理解并接受 GPLv3
        许可条款，您与本软件及其作者之间构成合同关系。如果您不同意这些条款，请勿使用本软件。
      </div>

      {/* Contributors */}
      <div style={{ marginBottom: 20 }}>
        <h2
          style={{
            fontSize: 14,
            fontWeight: 600,
            color: "var(--text-secondary)",
            marginBottom: 8,
          }}
        >
          贡献者
        </h2>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <a
            onClick={handleOpen("https://github.com/Hikari16665")}
            style={{
              fontSize: 13,
              color: "var(--accent)",
              textDecoration: "none",
              padding: "6px 14px",
              background: "var(--bg-secondary)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-sm)",
              cursor: "pointer",
            }}
          >
            Hikari16665
          </a>
        </div>
      </div>

      {/* GPLv3 Full Text */}
      <details
        style={{
          background: "var(--bg-secondary)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          overflow: "hidden",
        }}
      >
        <summary
          style={{
            padding: "12px 18px",
            fontSize: 13,
            fontWeight: 600,
            color: "var(--text-secondary)",
            cursor: "pointer",
            userSelect: "none",
          }}
        >
          查看 GPLv3 许可证全文
        </summary>
        <div
          style={{
            maxHeight: 300,
            overflow: "auto",
            borderTop: "1px solid var(--border)",
          }}
        >
          {licenseText ? (
            <pre
              style={{
                margin: 0,
                padding: "14px 18px",
                fontSize: 11,
                fontFamily: "var(--mono)",
                color: "var(--text-secondary)",
                whiteSpace: "pre-wrap",
                lineHeight: 1.6,
              }}
            >
              {licenseText}
            </pre>
          ) : licenseError ? (
            <div
              style={{
                padding: "14px 18px",
                fontSize: 13,
                color: "var(--red)",
              }}
            >
              {licenseError}
            </div>
          ) : (
            <div
              style={{
                padding: "14px 18px",
                fontSize: 13,
                color: "var(--text-muted)",
              }}
            >
              加载中...
            </div>
          )}
        </div>
      </details>
    </motion.div>
  );
}
