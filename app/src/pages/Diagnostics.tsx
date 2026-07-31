import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import type { DiagnosticLevel, DiagnosticReport, Server } from "../lib/types";
import { useToastStore } from "../store/toast";

const levelMeta: Record<DiagnosticLevel, { label: string; mark: string }> = {
  exception: { label: "异常", mark: "×" },
  severe_warning: { label: "严重警告", mark: "!" },
  warning: { label: "警告", mark: "!" },
  info: { label: "信息", mark: "i" },
};

export default function Diagnostics() {
  const addToast = useToastStore((state) => state.addToast);
  const [servers, setServers] = useState<Server[]>([]);
  const [serverId, setServerId] = useState("");
  const [report, setReport] = useState<DiagnosticReport | null>(null);
  const [running, setRunning] = useState(false);
  const selected = useMemo(() => servers.find((server) => server.uuid === serverId), [servers, serverId]);

  useEffect(() => {
    api.get<{ servers: Server[] }>("/api/servers")
      .then(({ servers }) => setServers(servers))
      .catch((error) => addToast(error.message || "无法读取服务器", "error"));
  }, [addToast]);

  async function run() {
    if (!serverId) return;
    setRunning(true);
    setReport(null);
    try {
      const result = await api.post<DiagnosticReport>(`/api/servers/${serverId}/diagnostics`);
      setReport(result);
      addToast(result.healthy ? "检测完成，未发现需要处理的问题" : `检测完成，发现 ${result.issues.length} 项结果`, result.healthy ? "success" : "info");
    } catch (error: any) {
      addToast(error.message || "检测失败", "error", error.detail);
    } finally {
      setRunning(false);
    }
  }

  return <section className="page-shell diagnostics-page">
    <header className="utility-header">
      <div><h1>服务器检测</h1><p>检查启动条件、安全配置、性能参数以及附加兼容性</p></div>
      <div className="header-actions">
        <select value={serverId} onChange={(event) => { setServerId(event.target.value); setReport(null); }}>
          <option value="">选择服务器…</option>
          {servers.map((server) => <option key={server.uuid} value={server.uuid}>{server.name} · {server.server_type}</option>)}
        </select>
        <button className="btn-primary" onClick={run} disabled={!serverId || running}>{running ? "正在检测…" : "开始检测"}</button>
      </div>
    </header>

    {!serverId ? <div className="workspace-placeholder"><strong>选择一个服务器开始检测</strong><span>检测过程仅读取本地文件，不会修改服务器配置。</span></div>
      : running ? <div className="diagnostic-running"><span className="diagnostic-spinner"/><strong>正在扫描 {selected?.name}</strong><p>读取配置文件并分析模组、插件元数据与依赖关系…</p></div>
      : !report ? <div className="diagnostic-ready"><div className="diagnostic-ready-icon">✓</div><div><strong>{selected?.name}</strong><span>已准备好。点击“开始检测”生成新的诊断报告。</span></div></div>
      : <div className="diagnostic-workspace">
        <aside className="diagnostic-summary">
          <div className={`diagnostic-verdict ${report.healthy ? "healthy" : "attention"}`}><span>{report.healthy ? "✓" : "!"}</span><strong>{report.healthy ? "状态良好" : "需要处理"}</strong><small>扫描 {report.addon_count} 个附加 · {report.duration_ms} ms</small></div>
          <div className="diagnostic-counts">{(Object.keys(levelMeta) as DiagnosticLevel[]).map((level) => <div key={level} className={`diagnostic-count level-${level}`}><span>{levelMeta[level].label}</span><strong>{report.summary[level]}</strong></div>)}</div>
          <small className="diagnostic-time">检测时间 {new Date(report.checked_at * 1000).toLocaleString()}</small>
        </aside>
        <main className="diagnostic-results">
          <div className="diagnostic-results-head"><strong>检测结果</strong><span>{report.issues.length ? `共 ${report.issues.length} 项` : "没有发现问题"}</span></div>
          {!report.issues.length ? <div className="diagnostic-empty"><strong>所有检查均已通过</strong><span>没有发现启动、安全、兼容性或配置方面的问题。</span></div>
            : report.issues.map((issue, index) => <article className={`diagnostic-issue level-${issue.level}`} key={`${issue.code}-${issue.file || index}`}>
              <span className="diagnostic-mark">{levelMeta[issue.level].mark}</span>
              <div><div className="diagnostic-issue-title"><span>{levelMeta[issue.level].label}</span><strong>{issue.title}</strong>{issue.file ? <code>{issue.file}</code> : null}</div><p>{issue.message}</p></div>
            </article>)}
        </main>
      </div>}
  </section>;
}
