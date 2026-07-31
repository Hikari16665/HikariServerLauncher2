import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { openUrl } from "@tauri-apps/plugin-opener";
import { api } from "../lib/api";

const BUILD_HASH = "TODO";

export default function About() {
  const [licenseText, setLicenseText] = useState<string | null>(null);
  const [licenseError, setLicenseError] = useState<string | null>(null);
  useEffect(() => { api.get<{ text: string }>("/api/system/license").then((data) => setLicenseText(data.text)).catch((error) => setLicenseError(error.message || "无法加载许可证文本")); }, []);

  return <motion.section className="page-shell" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
    <header className="page-header"><div><span className="page-kicker">APPLICATION</span><h1>关于 HSL</h1><p>项目版本、开源许可和维护信息。</p></div></header>
    <div className="page-body about-layout">
      <aside className="surface about-product">
        <img src="/HSL.png" alt="HSL" />
        <div><h2>Hikari Server Launcher 2</h2><p>轻量、直观的 Minecraft 服务端管理工具。</p></div>
        <span className="build-tag">Build {BUILD_HASH}</span>
        <button className="btn-ghost" onClick={() => openUrl("https://github.com/Hikari16665")}>访问项目主页</button>
      </aside>
      <div className="about-content">
        <article className="surface content-card"><span className="section-label">OPEN SOURCE</span><h2>GNU GPL v3.0</h2><p>本软件依据 GNU General Public License v3.0 发布。你可以在许可证允许的范围内使用、研究、修改和分发本软件。</p></article>
        <article className="surface content-card"><span className="section-label">MAINTAINER</span><h2>贡献者</h2><button className="link-chip" onClick={() => openUrl("https://github.com/Hikari16665")}>Hikari16665</button></article>
        <details className="surface license-panel"><summary>查看 GPLv3 许可证全文</summary><div className="license-content">{licenseText ? <pre>{licenseText}</pre> : licenseError ? <p className="error-text">{licenseError}</p> : <p>正在加载许可证……</p>}</div></details>
      </div>
    </div>
  </motion.section>;
}
