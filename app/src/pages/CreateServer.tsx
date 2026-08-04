import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import type { VersionInfo, ServerType } from "../lib/types";
import { useToastStore } from "../store/toast";

const SERVER_TYPES: ServerType[] = [
  "Vanilla",
  "Paper",
  "Forge",
  "Fabric",
  "NeoForge",
  "April",
];
const NEEDS_MC_VERSION: ServerType[] = ["Forge", "NeoForge", "Paper"];

function mapVersions(type: ServerType, data: any): VersionInfo[] {
  if (type === "Vanilla" || type === "Paper")
    return (data.releases || []).map((item: any) => ({
      id: item.id,
      type: item.type || "release",
      release_time: item.release_time || "",
    }));
  if (type === "Forge")
    return (data.mc_versions || data.forge_versions || []).map(
      (item: string) => ({ id: item, type: "release", release_time: "" }),
    );
  if (type === "NeoForge")
    return (data.mc_versions || data.neoforge_versions || []).map(
      (item: string) => ({ id: item, type: "release", release_time: "" }),
    );
  if (type === "Fabric")
    return (data.mc_versions || []).map((item: any) => ({
      id: item.version || item,
      type: "release",
      release_time: "",
    }));
  return (data.versions || []).map((item: any) => ({
    id: item.name || item.version,
    type: "release",
    release_time: "",
  }));
}

function mapBuilds(type: ServerType, data: any): VersionInfo[] {
  if (type === "Forge")
    return (data.forge_versions || []).map((item: any) => ({
      id: item.version,
      type: "release",
      release_time: data.mc_version || "",
    }));
  if (type === "NeoForge")
    return (data.neoforge_versions || []).map((item: any) => ({
      id: typeof item === "string" ? item : item.version || item.name || "",
      type: "release",
      release_time: data.mc_version || "",
    }));
  if (type === "Paper")
    return (data.sub_versions || []).map((item: any) => ({
      id: item.key,
      type: item.support_status === "SUPPORTED" ? "release" : "experimental",
      release_time: item.support_end || "",
    }));
  return [];
}

export default function CreateServer() {
  const navigate = useNavigate();
  const addToast = useToastStore((state) => state.addToast);
  const [name, setName] = useState("");
  const [serverType, setServerType] = useState<ServerType>("Vanilla");
  const [version, setVersion] = useState("");
  const [mcVersion, setMcVersion] = useState("");
  const [versions, setVersions] = useState<VersionInfo[]>([]);
  const [builds, setBuilds] = useState<VersionInfo[]>([]);
  const [maxMemory, setMaxMemory] = useState(2048);
  const [javaVersion, setJavaVersion] = useState("21");
  const [recommendedJava, setRecommendedJava] = useState(21);
  const [javaWarning, setJavaWarning] = useState(false);
  const [extraArgs, setExtraArgs] = useState("");
  const [filter, setFilter] = useState("");
  const [creating, setCreating] = useState(false);
  const [loadingVersions, setLoadingVersions] = useState(false);
  const [loadingBuilds, setLoadingBuilds] = useState(false);
  const [stableOnly, setStableOnly] = useState(true);
  const [error, setError] = useState("");
  const [stage, setStage] = useState(0);

  useEffect(() => {
    setVersion("");
    setMcVersion("");
    setBuilds([]);
    setFilter("");
    setLoadingVersions(true);
    api
      .get<any>(`/api/versions/${serverType.toLowerCase()}`)
      .then((data) => {
        const items = mapVersions(serverType, data);
        setVersions(items);
        if (!NEEDS_MC_VERSION.includes(serverType) && items[0])
          setVersion(items[0].id);
      })
      .catch((reason) => {
        setVersions([]);
        addToast("加载版本列表失败", "error", String(reason));
      })
      .finally(() => setLoadingVersions(false));
  }, [serverType, addToast]);

  useEffect(() => {
    if (!mcVersion || !NEEDS_MC_VERSION.includes(serverType)) return;
    setBuilds([]);
    setVersion("");
    setLoadingBuilds(true);
    api
      .get<any>(
        `/api/versions/${serverType.toLowerCase()}?mc_version=${encodeURIComponent(mcVersion)}`,
      )
      .then((data) => {
        const items = mapBuilds(serverType, data);
        setBuilds(items);
        if (items[0]) setVersion(items[0].id);
      })
      .catch((reason) => addToast("加载构建列表失败", "error", String(reason)))
      .finally(() => setLoadingBuilds(false));
  }, [mcVersion, serverType, addToast]);

  useEffect(() => {
    const selected = NEEDS_MC_VERSION.includes(serverType)
      ? mcVersion
      : version;
    if (!selected) return;
    api
      .get<{ recommended_java: number }>(
        `/api/versions/recommended-java?mc_version=${encodeURIComponent(selected)}`,
      )
      .then((data) => {
        setRecommendedJava(data.recommended_java);
        setJavaVersion(String(data.recommended_java));
        setJavaWarning(false);
      })
      .catch(() => undefined);
  }, [mcVersion, version, serverType]);

  const visibleVersions = useMemo(
    () =>
      versions
        .filter((item) => item.id.toLowerCase().includes(filter.toLowerCase()))
        .slice(0, 100),
    [versions, filter],
  );
  const canCreate = Boolean(
    name.trim() &&
      version &&
      (!NEEDS_MC_VERSION.includes(serverType) || mcVersion) &&
      maxMemory >= 512,
  );
  const versionReady = Boolean(
    version && (!NEEDS_MC_VERSION.includes(serverType) || mcVersion),
  );

  async function createServer() {
    if (!name.trim()) {
      setError("请输入服务器名称");
      return;
    }
    if (!version || (NEEDS_MC_VERSION.includes(serverType) && !mcVersion)) {
      setError("请选择完整的服务端版本");
      return;
    }
    setCreating(true);
    setError("");
    try {
      let finalVersion = NEEDS_MC_VERSION.includes(serverType)
        ? `${mcVersion}|${version}`
        : version;
      if (serverType === "Paper") {
        const response = await api.get<{ builds: any[] }>(
          `/api/versions/paper/builds?version=${encodeURIComponent(version)}`,
        );
        const candidates = stableOnly
          ? (response.builds || []).filter(
              (item) => item.channel === "STABLE" || item.channel === "RELEASE",
            )
          : response.builds || [];
        if (!candidates.length)
          throw new Error("该版本没有符合条件的 Paper 构建");
        const latest = candidates.reduce((left, right) =>
          (left.created_at || "") > (right.created_at || "") ? left : right,
        );
        finalVersion = latest.download_url;
      }
      await api.post("/api/servers/create", {
        name: name.trim(),
        server_type: serverType,
        version: finalVersion,
        mc_version: mcVersion || version,
        max_memory: maxMemory,
        java_version: javaVersion,
        extra_args: extraArgs,
      });
      navigate("/");
    } catch (reason) {
      const message =
        reason instanceof ApiError
          ? reason.message
          : reason instanceof Error
            ? reason.message
            : "创建失败";
      setError(message);
      addToast(
        message,
        "error",
        reason instanceof ApiError ? reason.detail : String(reason),
      );
    } finally {
      setCreating(false);
    }
  }

  return (
    <section className="page-shell server-wizard-page">
      <header className="page-header">
        <div>
          <span className="page-kicker">NEW INSTANCE</span>
          <h1>新建服务器</h1>
          <p>安装服务器及其运行环境</p>
        </div>
        <div className="import-steps">
          <span className={stage >= 0 ? "active" : ""}>1 基本信息</span>
          <span className={stage >= 1 ? "active" : ""}>2 服务端版本</span>
          <span className={stage >= 2 ? "active" : ""}>3 运行环境</span>
        </div>
      </header>
      <div className="page-body server-wizard">
        {stage === 0 && <article className="surface server-wizard-card">
          <SectionTitle step="01" label="IDENTITY" title="设置服务器名称和类型" />
          <p className="wizard-description">名称用于区分本地实例；服务端类型决定可用版本、模组或插件环境。</p>
          <div className="form-grid form-grid-name">
            <label>服务器名称<input value={name} onChange={(event) => setName(event.target.value)} placeholder="My Server" autoFocus /></label>
            <label>服务端类型<select value={serverType} onChange={(event) => setServerType(event.target.value as ServerType)}>{SERVER_TYPES.map((type) => <option key={type}>{type}</option>)}</select></label>
          </div>
          <footer className="server-wizard-actions"><button className="btn-ghost" onClick={() => navigate("/")}>取消</button><button className="btn-primary" disabled={!name.trim()} onClick={() => setStage(1)}>下一步：选择版本</button></footer>
        </article>}

        {stage === 1 && <article className="surface server-wizard-card version-section">
            <div className="section-heading">
              <SectionTitle
                step="02"
                label="VERSION"
                title={
                  NEEDS_MC_VERSION.includes(serverType)
                    ? "选择 Minecraft 版本"
                    : "选择服务端版本"
                }
              />
              <input
                className="version-search"
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
                placeholder="筛选版本…"
              />
            </div>
            <p className="wizard-description">只显示当前服务端类型可安装的版本。可输入版本号快速筛选。</p>
            {loadingVersions ? (
              <div className="inline-empty">正在加载版本…</div>
            ) : (
              <div className="version-picker">
                {visibleVersions.map((item) => {
                  const active = NEEDS_MC_VERSION.includes(serverType)
                    ? mcVersion === item.id
                    : version === item.id;
                  return (
                    <button
                      key={item.id}
                      className={`version-choice ${active ? "active" : ""}`}
                      onClick={() =>
                        NEEDS_MC_VERSION.includes(serverType)
                          ? setMcVersion(item.id)
                          : setVersion(item.id)
                      }
                    >
                      {item.id}
                    </button>
                  );
                })}
              </div>
            )}
          {NEEDS_MC_VERSION.includes(serverType) && mcVersion && <div className="wizard-build-panel">
              <div className="section-heading">
                <SectionTitle
                  step="02B"
                  label="BUILD"
                  title={`选择 ${serverType} 构建`}
                />
                {loadingBuilds && <span className="muted-text">加载中…</span>}
              </div>
              <div className="version-picker compact">
                {builds.map((item) => (
                  <button
                    key={item.id}
                    className={`version-choice ${version === item.id ? "active" : ""}`}
                    onClick={() => setVersion(item.id)}
                  >
                    {item.id}
                  </button>
                ))}
              </div>
              {serverType === "Paper" && (
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={!stableOnly}
                    onChange={(event) => setStableOnly(!event.target.checked)}
                  />
                  允许使用非稳定构建
                </label>
              )}
            </div>}
          <footer className="server-wizard-actions"><button className="btn-ghost" onClick={() => setStage(0)}>上一步</button><button className="btn-primary" disabled={!versionReady} onClick={() => setStage(2)}>下一步：运行环境</button></footer>
        </article>}

        {stage === 2 && <article className="surface server-wizard-card">
          <SectionTitle step="03" label="RUNTIME" title="配置运行环境" />
          <p className="wizard-description">Java 已根据 Minecraft 版本自动推荐；需要时可调整内存和 JVM 参数。</p>
          <div className="server-runtime-grid">
            <div className="form-stack">
              <label>最大内存（MB）<input type="number" min="512" step="512" value={maxMemory} onChange={(event) => setMaxMemory(Number(event.target.value))} /></label>
              <label>Java 版本<select value={javaVersion} onChange={(event) => { const value = event.target.value; setJavaVersion(value); setJavaWarning(Number(value) !== recommendedJava); }}>{["8", "11", "17", "21", "25"].map((item) => <option key={item} value={item}>Java {item}</option>)}</select></label>
              {javaWarning && <p className="warning-text">当前不是推荐的 Java {recommendedJava}，服务端可能无法启动。</p>}
              <label>额外 JVM 参数<input value={extraArgs} onChange={(event) => setExtraArgs(event.target.value)} placeholder="-Xms512M -XX:+UseG1GC" /></label>
            </div>
            <div className="server-wizard-summary"><span className="section-label">INSTALL SUMMARY</span><dl><Summary label="名称" value={name || "未命名"} /><Summary label="类型" value={serverType} /><Summary label="Minecraft" value={mcVersion || version} /><Summary label="构建" value={version} /><Summary label="Java" value={`Java ${javaVersion}`} /><Summary label="内存" value={`${maxMemory} MB`} /></dl></div>
          </div>
          {error && <p className="error-banner">{error}</p>}
          <footer className="server-wizard-actions"><button className="btn-ghost" onClick={() => setStage(1)}>上一步</button><button className="btn-primary" onClick={createServer} disabled={creating || !canCreate}>{creating ? "正在创建…" : "创建服务器"}</button></footer>
        </article>}
      </div>
    </section>
  );
}

function SectionTitle({
  step,
  label,
  title,
}: {
  step?: string;
  label: string;
  title: string;
}) {
  return (
    <div className="section-title">
      <span className="section-label">
        {step ? `${step} · ` : ""}
        {label}
      </span>
      <h2>{title}</h2>
    </div>
  );
}
function Summary({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
