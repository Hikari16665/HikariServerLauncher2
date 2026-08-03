import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../lib/api";
import type { MarketProject, MarketVersion, Server } from "../lib/types";
import { useToastStore } from "../store/toast";

type MarketInfo = {
  project_type: string;
  loader: string;
  folder: string;
  game_version: string;
};
type Category = { name: string; header: string };

export default function Market() {
  const addToast = useToastStore((state) => state.addToast);
  const [servers, setServers] = useState<Server[]>([]);
  const [serverId, setServerId] = useState("");
  const [info, setInfo] = useState<MarketInfo | null>(null);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [sort, setSort] = useState("relevance");
  const [categories, setCategories] = useState<Category[]>([]);
  const [projects, setProjects] = useState<MarketProject[]>([]);
  const [selected, setSelected] = useState<MarketProject | null>(null);
  const [versions, setVersions] = useState<MarketVersion[]>([]);
  const [version, setVersion] = useState<MarketVersion | null>(null);
  const [details, setDetails] = useState<MarketVersion | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingInfo, setLoadingInfo] = useState(false);
  const [loadingVersions, setLoadingVersions] = useState(false);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [marketError, setMarketError] = useState("");
  const [dependencyView, setDependencyView] = useState(false);
  const infoRequestRef = useRef(0);
  const searchRequestRef = useRef(0);
  const projectRequestRef = useRef(0);
  const versionRequestRef = useRef(0);
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
  }, []);
  useEffect(() => {
    const requestId = ++infoRequestRef.current;
    searchRequestRef.current += 1;
    projectRequestRef.current += 1;
    versionRequestRef.current += 1;
    setDependencyView(false);
    setSelected(null);
    setVersions([]);
    setVersion(null);
    setDetails(null);
    setMarketError("");
    if (!serverId) {
      setInfo(null);
      setProjects([]);
      setCategories([]);
      return;
    }
    setLoadingInfo(true);
    Promise.all([
      api.get<MarketInfo>(`/api/market/server/${serverId}`),
      api.get<{ categories: Category[] }>(`/api/market/categories/${serverId}`),
    ])
      .then(([meta, tags]) => {
        if (requestId !== infoRequestRef.current) return;
        setInfo(meta);
        setCategories(tags.categories);
        setCategory("");
        setSelected(null);
        setVersion(null);
      })
      .catch((error) => {
        if (requestId !== infoRequestRef.current) return;
        setInfo(null);
        setProjects([]);
        setMarketError(error.message || "无法读取市场信息");
        addToast(error.message || "无法读取市场信息", "error");
      })
      .finally(() => {
        if (requestId === infoRequestRef.current) setLoadingInfo(false);
      });
  }, [serverId]);
  useEffect(() => {
    if (info) search();
  }, [info, category, sort]);
  async function search() {
    if (!serverId || !info) return;
    const requestId = ++searchRequestRef.current;
    setDependencyView(false);
    setMarketError("");
    setLoading(true);
    try {
      const data = await api.get<{ hits: MarketProject[] }>(
        `/api/market/search?server_uuid=${encodeURIComponent(serverId)}&query=${encodeURIComponent(query)}&category=${encodeURIComponent(category)}&index=${sort}&limit=40`,
      );
      if (requestId !== searchRequestRef.current) return;
      setProjects(data.hits);
      setSelected(null);
      setVersions([]);
      setVersion(null);
      setDetails(null);
    } catch (error: any) {
      if (requestId !== searchRequestRef.current) return;
      setProjects([]);
      setMarketError(error.message || "搜索失败");
      addToast(error.message || "搜索失败", "error");
    } finally {
      if (requestId === searchRequestRef.current) setLoading(false);
    }
  }
  async function chooseProject(project: MarketProject) {
    const requestId = ++projectRequestRef.current;
    versionRequestRef.current += 1;
    setSelected(project);
    setVersions([]);
    setVersion(null);
    setDetails(null);
    setLoadingVersions(true);
    try {
      const data = await api.get<{ versions: MarketVersion[] }>(
        `/api/market/projects/${project.project_id}/versions?server_uuid=${serverId}`,
      );
      if (requestId === projectRequestRef.current) setVersions(data.versions);
    } catch (error: any) {
      if (requestId !== projectRequestRef.current) return;
      addToast(error.message || "无法读取兼容版本", "error");
    } finally {
      if (requestId === projectRequestRef.current) setLoadingVersions(false);
    }
  }
  async function chooseVersion(item: MarketVersion | null) {
    const requestId = ++versionRequestRef.current;
    setVersion(item);
    setDetails(null);
    if (!item) return;
    setLoadingDetails(true);
    try {
      const result = await api.get<MarketVersion>(
        `/api/market/versions/${item.id}?server_uuid=${serverId}`,
      );
      if (requestId === versionRequestRef.current) setDetails(result);
    } catch (error: any) {
      if (requestId !== versionRequestRef.current) return;
      addToast(error.message || "无法解析依赖", "error");
    } finally {
      if (requestId === versionRequestRef.current) setLoadingDetails(false);
    }
  }
  async function install() {
    if (!version || !details || installing) return;
    setInstalling(true);
    try {
      await api.post("/api/market/install", {
        server_uuid: serverId,
        version_id: version.id,
        install_dependencies: true,
      });
      const deps = details?.required_dependencies || [];
      addToast(
        "安装任务已创建",
        "success",
        deps.length ? `将同时安装 ${deps.length} 个前置` : undefined,
      );
      if (deps.length) {
        setProjects(
          deps.map((item) => ({
            project_id: item.project_id,
            slug: item.project_id,
            title: item.title,
            description: item.description,
            author: "依赖项",
            icon_url: item.icon_url,
            categories: item.categories,
            display_categories: item.categories,
            versions: item.version.game_versions,
            downloads: 0,
            server_side: "required",
            project_type: info?.project_type || "mod",
          })),
        );
        setDependencyView(true);
        setSelected(null);
        setVersion(null);
        setDetails(null);
      }
    } catch (error: any) {
      addToast(error.message || "无法创建安装任务", "error");
    } finally {
      setInstalling(false);
    }
  }
  const groupedCategories = useMemo(
    () => categories.filter((item) => item.header !== "resolutions"),
    [categories],
  );
  return (
    <section className="page-shell market-page">
      <header className="utility-header">
        <div>
          <h1>{dependencyView ? "正在安装的前置" : "市场"}</h1>
          <p>
            {dependencyView
              ? "以下前置已加入同一下载任务"
              : "从 Modrinth 安装与当前服务器兼容的模组或插件"}
          </p>
        </div>
        <select value={serverId} onChange={(e) => setServerId(e.target.value)}>
          <option value="">选择服务器…</option>
          {servers.map((server) => (
            <option key={server.uuid} value={server.uuid}>
              {server.name} · {server.server_type}
            </option>
          ))}
        </select>
      </header>
      {!serverId ? (
        <div className="workspace-placeholder">
          <strong>先选择一个服务器</strong>
          <span>
            系统会根据 Forge、NeoForge、Fabric 或 Paper
            自动切换市场类型和安装目录。
          </span>
        </div>
      ) : loadingInfo ? (
        <div className="workspace-placeholder" role="status">
          <strong>正在读取服务器环境…</strong>
          <span>正在确认加载器、游戏版本和安装目录。</span>
        </div>
      ) : marketError && !info ? (
        <div className="workspace-placeholder">
          <strong>无法打开市场</strong>
          <span>{marketError}</span>
        </div>
      ) : (
        <div className="market-layout">
          <aside className="market-filters">
            <div className="filter-summary">
              <strong>
                {info?.project_type === "plugin" ? "插件" : "模组"}
              </strong>
              <span>
                {info?.loader} · Minecraft {info?.game_version || "未知版本"}
              </span>
              <small>安装到 /{info?.folder}</small>
            </div>
            <label>
              分类
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                <option value="">全部分类</option>
                {groupedCategories.map((item) => (
                  <option key={item.name} value={item.name}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              排序
              <select value={sort} onChange={(e) => setSort(e.target.value)}>
                <option value="relevance">相关度</option>
                <option value="downloads">下载量</option>
                <option value="updated">最近更新</option>
                <option value="newest">最新发布</option>
              </select>
            </label>
          </aside>
          <main className="market-results">
            <div className="market-search">
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && search()}
                placeholder="搜索名称、作者或关键词…"
              />
              <button className="btn-primary" disabled={loading} onClick={search}>
                {loading ? "搜索中…" : "搜索"}
              </button>
            </div>
            <div className="project-list">
              {loading ? (
                <div className="table-empty">正在搜索…</div>
              ) : projects.length === 0 ? (
                <div className="table-empty">
                  <strong>{marketError ? "搜索失败" : "没有找到兼容项目"}</strong>
                  <span>{marketError || "尝试更换关键词、分类或排序方式。"}</span>
                </div>
              ) : (
                projects.map((project) => (
                  <button
                    key={project.project_id}
                    className={`project-row ${selected?.project_id === project.project_id ? "active" : ""}`}
                    onClick={() => chooseProject(project)}
                  >
                    {project.icon_url ? (
                      <img src={project.icon_url} alt="" />
                    ) : (
                      <span className="project-icon-placeholder">◇</span>
                    )}
                    <span className="project-main">
                      <strong>{project.title}</strong>
                      <small>{project.description}</small>
                      <em>
                        {project.author} · {project.downloads.toLocaleString()}{" "}
                        次下载
                      </em>
                    </span>
                    <span className="category-tags">
                      {project.display_categories?.slice(0, 3).map((item) => (
                        <i key={item}>{item}</i>
                      ))}
                    </span>
                  </button>
                ))
              )}
            </div>
          </main>
          <aside className="market-inspector">
            {!selected ? (
              <div className="inspector-empty">选择一个项目查看兼容版本</div>
            ) : (
              <>
                <div className="inspector-project">
                  {selected.icon_url && <img src={selected.icon_url} alt="" />}
                  <div>
                    <h2>{selected.title}</h2>
                    <p>{selected.description}</p>
                  </div>
                </div>
                <label>
                  兼容版本
                  <select
                    disabled={loadingVersions}
                    value={version?.id || ""}
                    onChange={(e) =>
                      chooseVersion(
                        versions.find((item) => item.id === e.target.value) ||
                          null,
                      )
                    }
                  >
                    <option value="">
                      {loadingVersions ? "正在读取兼容版本…" : "选择版本…"}
                    </option>
                    {versions.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.version_number} · {item.version_type}
                      </option>
                    ))}
                  </select>
                </label>
                {version && (
                  <dl className="version-facts">
                    <div>
                      <dt>加载器</dt>
                      <dd>{version.loaders.join(", ")}</dd>
                    </div>
                    <div>
                      <dt>游戏版本</dt>
                      <dd>{version.game_versions.join(", ")}</dd>
                    </div>
                    <div>
                      <dt>发布时间</dt>
                      <dd>
                        {new Date(version.date_published).toLocaleDateString()}
                      </dd>
                    </div>
                  </dl>
                )}
                {details?.required_dependencies &&
                  details.required_dependencies.length > 0 && (
                    <div className="dependency-list">
                      <h3>需要同时安装</h3>
                      {details.required_dependencies.map((item) => (
                        <div key={item.project_id}>
                          {item.icon_url ? (
                            <img src={item.icon_url} alt="" />
                          ) : (
                            <span />
                          )}
                          <p>
                            <strong>{item.title}</strong>
                            <small>{item.version.version_number}</small>
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                <button
                  className="btn-primary install-addon-button"
                  disabled={!version || !details || loadingDetails || installing}
                  onClick={install}
                >
                  {installing ? "正在创建任务…" : loadingDetails ? "正在检查前置…" : "安装"}
                  {details?.required_dependencies?.length
                    ? `（含 ${details.required_dependencies.length} 个前置）`
                    : ""}
                </button>
              </>
            )}
          </aside>
        </div>
      )}
    </section>
  );
}
