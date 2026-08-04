import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { InstalledAddon, Server } from "../lib/types";
import { showConfirm } from "../components/ConfirmDialog";
import { useToastStore } from "../store/toast";

export default function Addons() {
  const addToast = useToastStore((state) => state.addToast);
  const [servers, setServers] = useState<Server[]>([]);
  const [serverId, setServerId] = useState("");
  const [addons, setAddons] = useState<InstalledAddon[]>([]);
  const [folder, setFolder] = useState("");
  const [selected, setSelected] = useState<InstalledAddon | null>(null);
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [acting, setActing] = useState(false);
  const [loadError, setLoadError] = useState("");
  const loadRequestRef = useRef(0);
  useEffect(() => {
    api
      .get<{ servers: Server[] }>("/api/servers")
      .then(({ servers }) =>
        setServers(
          servers.filter((item) =>
            ["Forge", "NeoForge", "Fabric", "Paper"].includes(item.server_type),
          ),
        ),
      )
      .catch((error) =>
        addToast(error.message || "无法读取服务器列表", "error"),
      );
  }, [addToast]);
  const load = useCallback(async () => {
    if (!serverId) return;
    const requestId = ++loadRequestRef.current;
    setLoadError("");
    setLoading(true);
    try {
      const data = await api.get<{ addons: InstalledAddon[]; folder: string }>(
        `/api/servers/${serverId}/addons`,
      );
      if (requestId !== loadRequestRef.current) return;
      setAddons(data.addons);
      setFolder(data.folder);
      setSelected(null);
    } catch (error: any) {
      if (requestId !== loadRequestRef.current) return;
      setAddons([]);
      setSelected(null);
      setLoadError(error.message || "无法读取附加");
      addToast(error.message || "无法读取附加", "error");
    } finally {
      if (requestId === loadRequestRef.current) setLoading(false);
    }
  }, [serverId, addToast]);
  useEffect(() => {
    loadRequestRef.current += 1;
    setAddons([]);
    setSelected(null);
    setFolder("");
    setLoadError("");
    load();
  }, [serverId, load]);
  function select(item: InstalledAddon) {
    setSelected(item);
    setName(item.name);
  }
  async function update(data: { enabled?: boolean; name?: string }) {
    if (!selected || acting) return;
    setActing(true);
    try {
      await api.put(
        `/api/servers/${serverId}/addons/${encodeURIComponent(selected.filename)}`,
        data,
      );
      await load();
      addToast("附加已更新", "success");
    } catch (error: any) {
      addToast(error.message || "更新失败", "error");
    } finally {
      setActing(false);
    }
  }
  async function remove() {
    if (
      !selected ||
      acting ||
      !(await showConfirm(`确定删除“${selected.name}”吗？`))
    )
      return;
    setActing(true);
    try {
      await api.delete(
        `/api/servers/${serverId}/addons/${encodeURIComponent(selected.filename)}`,
      );
      await load();
      addToast("附加已删除", "success");
    } catch (error: any) {
      addToast(error.message || "删除失败", "error");
    } finally {
      setActing(false);
    }
  }
  return (
    <section className="page-shell addons-page">
      <header className="utility-header">
        <div>
          <h1>附加管理</h1>
          <p>管理服务器中的模组和插件</p>
        </div>
        <div className="header-actions">
          <select
            value={serverId}
            onChange={(e) => setServerId(e.target.value)}
          >
            <option value="">选择服务器…</option>
            {servers.map((server) => (
              <option key={server.uuid} value={server.uuid}>
                {server.name} · {server.server_type}
              </option>
            ))}
          </select>
          <button className="btn-ghost" onClick={load} disabled={!serverId || loading}>
            {loading ? "扫描中…" : "刷新"}
          </button>
        </div>
      </header>
      {!serverId ? (
        <div className="workspace-placeholder">
          <strong>选择服务器以查看附加</strong>
          <span>
            Forge、NeoForge 和 Fabric 读取 mods；Paper 读取 plugins
          </span>
        </div>
      ) : (
        <div className="addon-layout">
          <main className="addon-list">
            <div className="addon-list-head">
              <span>名称</span>
              <span>版本</span>
              <span>状态</span>
              <span>文件大小</span>
              <span>文件</span>
            </div>
            {loading ? (
              <div className="table-empty">正在扫描 /{folder}…</div>
            ) : loadError ? (
              <div className="table-empty">
                <strong>扫描失败</strong>
                <span>{loadError}</span>
              </div>
            ) : addons.length === 0 ? (
              <div className="table-empty">
                <strong>/{folder} 中没有附加</strong>
                <span>可从市场安装模组或插件</span>
              </div>
            ) : (
              addons.map((item) => (
                <button
                  key={item.filename}
                  className={`addon-row ${selected?.filename === item.filename ? "active" : ""}`}
                  onClick={() => select(item)}
                >
                  <span className="addon-name">
                    {item.embedded_icon || item.icon_url ? (
                      <img src={item.embedded_icon || item.icon_url} alt="" />
                    ) : (
                      <i>◇</i>
                    )}
                    <strong>{item.name}</strong>
                  </span>
                  <span>{item.version || "—"}</span>
                  <span
                    className={item.enabled ? "success-text" : "muted-text"}
                  >
                    {item.enabled ? "已启用" : "已停用"}
                  </span>
                  <span>{formatBytes(item.size)}</span>
                  <span className="mono-cell">{item.filename}</span>
                </button>
              ))
            )}
          </main>
          <aside className="addon-inspector">
            {selected ? (
              <>
                {selected.embedded_icon || selected.icon_url ? (
                  <img
                    className="addon-large-icon"
                    src={selected.embedded_icon || selected.icon_url}
                    alt=""
                  />
                ) : null}
                <h2>{selected.name}</h2>
                <p>{selected.description || "没有可用的说明信息。"}</p>
                <dl>
                  <div>
                    <dt>文件</dt>
                    <dd>{selected.filename}</dd>
                  </div>
                  <div>
                    <dt>版本</dt>
                    <dd>{selected.version || "未知"}</dd>
                  </div>
                  <div>
                    <dt>状态</dt>
                    <dd>{selected.enabled ? "已启用" : "已停用"}</dd>
                  </div>
                </dl>
                <label>
                  显示名称
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </label>
                <div className="addon-actions">
                  <button
                    className="btn-primary"
                    disabled={acting || !name.trim()}
                    onClick={() => update({ name })}
                  >
                    {acting ? "处理中…" : "保存名称"}
                  </button>
                  <button
                    className="btn-ghost"
                    disabled={acting}
                    onClick={() => update({ enabled: !selected.enabled })}
                  >
                    {selected.enabled ? "停用" : "启用"}
                  </button>
                  <button className="btn-danger" disabled={acting} onClick={remove}>
                    删除
                  </button>
                </div>
              </>
            ) : (
              <div className="inspector-empty">选择要管理的模组或插件</div>
            )}
          </aside>
        </div>
      )}
    </section>
  );
}
function formatBytes(value: number) {
  if (value > 1_048_576) return `${(value / 1_048_576).toFixed(1)} MB`;
  return `${Math.ceil(value / 1024)} KB`;
}
