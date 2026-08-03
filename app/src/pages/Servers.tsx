import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import type { Server, ServerStatus } from "../lib/types";
import { useToastStore } from "../store/toast";
import { showConfirm } from "../components/ConfirmDialog";

export default function Servers() {
  const navigate = useNavigate();
  const addToast = useToastStore((state) => state.addToast);
  const [servers, setServers] = useState<Server[]>([]);
  const [statuses, setStatuses] = useState<Record<string, ServerStatus>>({});
  const [statusErrors, setStatusErrors] = useState<Set<string>>(new Set());
  const [acting, setActing] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [stateFilter, setStateFilter] = useState<"all" | "running" | "stopped">("all");

  const load = () => api.get<{ servers: Server[] }>("/api/servers").then(({ servers }) => setServers(servers)).catch((error) => addToast("无法加载服务器", "error", error?.detail)).finally(() => setLoading(false));
  useEffect(() => { load(); }, []);
  useEffect(() => { if (!servers.length) return; const refresh = () => servers.forEach((server) => api.get<ServerStatus>(`/api/servers/${server.uuid}/status`).then((status) => { setStatuses((current) => ({ ...current, [server.uuid]: status })); setStatusErrors((current) => { const next = new Set(current); next.delete(server.uuid); return next; }); }).catch(() => setStatusErrors((current) => new Set(current).add(server.uuid)))); refresh(); const timer = setInterval(refresh, 5000); return () => clearInterval(timer); }, [servers]);

  const visible = useMemo(() => servers.filter((server) => {
    const status = statuses[server.uuid];
    const matchesState = stateFilter === "all" || (stateFilter === "running" ? status?.running === true : status?.running === false);
    return matchesState && `${server.name} ${server.server_type} ${server.uuid}`.toLowerCase().includes(query.toLowerCase());
  }), [servers, statuses, stateFilter, query]);

  async function runAction(server: Server, action: "start" | "stop" | "kill") { setActing((current) => new Set(current).add(server.uuid)); try { await api.post(`/api/servers/${server.uuid}/${action}`); const status = await api.get<ServerStatus>(`/api/servers/${server.uuid}/status`); setStatuses((current) => ({ ...current, [server.uuid]: status })); addToast(action === "start" ? "服务器已启动" : "已发送停止命令", "success"); } catch (error: any) { addToast(error.message || "操作失败", "error", error.detail); } finally { setActing((current) => { const next = new Set(current); next.delete(server.uuid); return next; }); } }
  async function removeServer(server: Server) { if (!await showConfirm(`确定删除“${server.name}”吗？服务器目录和文件将永久删除。`)) return; try { await api.delete(`/api/servers/${server.uuid}`); setServers((items) => items.filter((item) => item.uuid !== server.uuid)); addToast("服务器已删除", "success"); } catch (error: any) { addToast(error.message || "删除失败", "error", error.detail); } }

  return <section className="page-shell server-list-page">
    <header className="utility-header"><div><h1>服务器</h1><p>{servers.length} 个实例 · {Object.values(statuses).filter((s) => s.running).length} 个运行中</p></div><button className="btn-primary" onClick={() => navigate("/install")}>安装服务器</button></header>
    <div className="tool-row"><input className="table-search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索名称、类型或标识…" /><div className="segmented">{(["all", "running", "stopped"] as const).map((item) => <button key={item} className={stateFilter === item ? "active" : ""} onClick={() => setStateFilter(item)}>{item === "all" ? "全部" : item === "running" ? "运行中" : "已停止"}</button>)}</div><button className="btn-ghost" onClick={load}>刷新</button></div>
    <div className="data-panel">
      <div className="server-table server-table-head"><span>服务器</span><span>类型</span><span>状态</span><span>内存</span><span>进程</span><span>标识</span><span>操作</span></div>
      {loading ? <div className="table-empty">正在读取服务器…</div> : visible.length === 0 ? <div className="table-empty"><strong>{servers.length ? "没有匹配的服务器" : "还没有服务器"}</strong><span>{servers.length ? "请调整搜索或筛选条件" : "点击右上角“安装服务器”创建第一个实例"}</span></div> : visible.map((server) => { const status = statuses[server.uuid]; const unknown = !status || statusErrors.has(server.uuid); const running = status?.running === true; const busy = acting.has(server.uuid); return <div className="server-table server-row" key={server.uuid} onDoubleClick={() => navigate(`/servers/${server.uuid}`)}><span className="server-cell-name"><i className={`status-dot ${running ? "running" : unknown ? "failed" : ""}`} /><strong>{server.name}</strong></span><span>{server.server_type}<small>Java {server.java_version}</small></span><span className={running ? "success-text" : unknown ? "error-text" : "muted-text"}>{unknown ? "状态未知" : running ? "运行中" : "已停止"}</span><span>{server.max_memory} MB</span><span className="mono-cell">{status?.pid ?? "—"}</span><span className="mono-cell">{server.uuid.slice(0, 8)}</span><span className="row-actions"><button className="btn-ghost" onClick={() => navigate(`/servers/${server.uuid}`)}>管理</button>{running ? <button className="btn-ghost" disabled={busy} onClick={() => runAction(server, "stop")}>{busy ? "处理中…" : "停止"}</button> : <button className="btn-success" disabled={busy || unknown} onClick={() => runAction(server, "start")}>{busy ? "处理中…" : "启动"}</button>}<button className="btn-danger" onClick={() => removeServer(server)} title="永久删除">删除</button></span></div>; })}
    </div>
  </section>;
}
