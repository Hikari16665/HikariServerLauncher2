import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import type { VersionInfo, ServerType } from "../lib/types";
import { useTaskStore } from "../store/tasks";
import { useToastStore } from "../store/toast";

const SERVER_TYPES: ServerType[] = [
  "Vanilla", "Paper", "Forge", "Fabric", "NeoForge", "April",
];

const NEEDS_MC_VERSION: ServerType[] = ["Forge", "NeoForge", "Paper"];

function mapVersions(type: ServerType, data: any): VersionInfo[] {
  switch (type) {
    case "Vanilla":
      return (data.releases || []).map((v: any) => ({
        id: v.id, type: v.type || "release", release_time: v.release_time || "",
      }));
    case "Paper":
      return (data.releases || []).map((v: any) => ({
        id: v.id, type: v.type || "release", release_time: v.release_time || "",
      }));
    case "Forge":
      return (data.mc_versions || data.forge_versions || []).map((v: string) => ({
        id: v, type: "release", release_time: "",
      }));
    case "NeoForge":
      return (data.mc_versions || data.neoforge_versions || []).map((v: string) => ({
        id: v, type: "release", release_time: "",
      }));
    case "Fabric":
      return (data.mc_versions || []).map((v: any) => ({
        id: v.version || v, type: "release", release_time: "",
      }));
    case "April":
      return (data.versions || []).map((v: any) => ({
        id: v.name || v.version, type: "release", release_time: "",
      }));
    default:
      return [];
  }
}

function mapSubVersions(type: ServerType, data: any): VersionInfo[] {
  switch (type) {
    case "Forge":
      return (data.forge_versions || []).map((v: any) => ({
        id: v.version, type: "release", release_time: data.mc_version || "",
      }));
    case "NeoForge":
      return (data.neoforge_versions || []).map((v: any) => ({
        id: typeof v === "string" ? v : v.version || v.name || "",
        type: "release", release_time: data.mc_version || "",
      }));
    case "Paper":
      return (data.sub_versions || []).map((sv: any) => ({
        id: sv.key,
        type: sv.support_status === "SUPPORTED" ? "release" : "experimental",
        release_time: sv.support_end || "",
      }));
    default:
      return [];
  }
}

const labelStyle: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  color: "var(--text-secondary)",
  display: "block",
  marginBottom: 5,
};

const sectionStyle: React.CSSProperties = {
  marginBottom: 18,
};

const versionGrid: React.CSSProperties = {
  maxHeight: 180,
  overflow: "auto",
  background: "var(--bg-secondary)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-sm)",
  padding: 4,
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))",
  gap: 3,
};

export default function CreateServer() {
  const [name, setName] = useState("");
  const [serverType, setServerType] = useState<ServerType>("Vanilla");
  const [version, setVersion] = useState("");
  const [mcVersion, setMcVersion] = useState("");
  const [versions, setVersions] = useState<VersionInfo[]>([]);
  const [subVersions, setSubVersions] = useState<VersionInfo[]>([]);
  const [maxMemory, setMaxMemory] = useState(2048);
  const [javaVersion, setJavaVersion] = useState("21");
  const [recommendedJava, setRecommendedJava] = useState(21);
  const [javaWarning, setJavaWarning] = useState(false);
  const [extraArgs, setExtraArgs] = useState("");
  const [filter, setFilter] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [loadingSub, setLoadingSub] = useState(false);
  const [stableOnly, setStableOnly] = useState(true);

  const navigate = useNavigate();
  const setTasks = useTaskStore((s) => s.setTasks);
  const addToast = useToastStore((s) => s.addToast);

  useEffect(() => {
    const typeKey = serverType.toLowerCase();
    setMcVersion("");
    setSubVersions([]);
    setFilter("");

    api
      .get<any>(`/api/versions/${typeKey}`)
      .then((data) => {
        const mapped = mapVersions(serverType, data);
        setVersions(mapped);
        if (!NEEDS_MC_VERSION.includes(serverType) && mapped.length > 0) {
          setVersion(mapped[0].id);
        } else {
          setVersion("");
        }
      })
      .catch((e) => {
        addToast("加载版本列表失败", "error", String(e));
        setVersions([]);
      });
  }, [serverType]);

  useEffect(() => {
    if (!mcVersion || !NEEDS_MC_VERSION.includes(serverType)) return;
    const typeKey = serverType.toLowerCase();
    setLoadingSub(true);
    setSubVersions([]);
    setVersion("");

    api
      .get<any>(`/api/versions/${typeKey}?mc_version=${encodeURIComponent(mcVersion)}`)
      .then((data) => {
        const mapped = mapSubVersions(serverType, data);
        setSubVersions(mapped);
        if (mapped.length > 0) setVersion(mapped[0].id);
      })
      .catch((e) => {
        addToast("加载版本列表失败", "error", String(e));
        setSubVersions([]);
      })
      .finally(() => setLoadingSub(false));
  }, [mcVersion, serverType]);

  // Auto-detect recommended Java version when MC version changes
  useEffect(() => {
    const mcVer = NEEDS_MC_VERSION.includes(serverType) ? mcVersion : version;
    if (!mcVer) return;
    api
      .get<{ recommended_java: number }>(
        `/api/versions/recommended-java?mc_version=${encodeURIComponent(mcVer)}`
      )
      .then((data) => {
        setRecommendedJava(data.recommended_java);
        setJavaVersion(String(data.recommended_java));
        setJavaWarning(false);
      })
      .catch(() => {});
  }, [mcVersion, version, serverType]);

  async function handleCreate() {
    if (!name.trim()) { setError("请输入服务器名称"); return; }
    if (!version) { setError("请选择版本"); return; }
    if (NEEDS_MC_VERSION.includes(serverType) && !mcVersion) {
      setError("请选择 Minecraft 版本"); return;
    }
    setCreating(true);
    setError("");

    let finalVersion: string;
    if (serverType === "Paper") {
      // Fetch builds and pick the appropriate one
      try {
        const buildsData = await api.get<{ builds: any[] }>(
          `/api/versions/paper/builds?version=${encodeURIComponent(version)}`
        );
        const builds = buildsData.builds || [];
        if (builds.length === 0) {
          setError("该版本没有可用构建");
          setCreating(false);
          return;
        }
        // Filter by channel if stableOnly
        const candidates = stableOnly
          ? builds.filter((b: any) => b.channel === "STABLE" || b.channel === "RELEASE")
          : builds;
        if (candidates.length === 0) {
          setError("该游戏版本没有 Paper 的稳定构建，可以尝试允许非稳定版本重新安装");
          setCreating(false);
          return;
        }
        // Pick latest by createdAt
        const latest = candidates.reduce((a: any, b: any) =>
          (a.created_at || "") > (b.created_at || "") ? a : b
        );
        finalVersion = latest.download_url;
      } catch (e: any) {
        setError(e.message || "获取 Paper 构建失败");
        setCreating(false);
        return;
      }
    } else if (NEEDS_MC_VERSION.includes(serverType) && mcVersion) {
      finalVersion = `${mcVersion}|${version}`;
    } else {
      finalVersion = version;
    }

    try {
      await api.post<{ task_id: string }>("/api/servers/create", {
        name: name.trim(), server_type: serverType, version: finalVersion,
        max_memory: maxMemory, java_version: javaVersion, extra_args: extraArgs,
      });
      const tasks = await api.get<{ tasks: any[] }>("/api/tasks");
      setTasks(tasks.tasks);
      navigate("/");
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
        addToast(e.message, "error", e.detail);
      } else {
        setError("创建失败");
        addToast("创建失败", "error", String(e));
      }
    } finally {
      setCreating(false);
    }
  }

  const filteredVersions = filter
    ? versions.filter((v) => v.id.includes(filter))
    : versions;

  const showSubSelector = NEEDS_MC_VERSION.includes(serverType) && mcVersion;

  return (
    <div style={{ padding: 24, maxWidth: 680, margin: "0 auto", width: "100%", height: "100%", overflow: "auto" }}>
      <h1 style={{ fontSize: 20, fontWeight: 600, color: "var(--text-primary)", marginBottom: 24 }}>
        安装服务器
      </h1>

      {/* Name & Type */}
      <div style={sectionStyle}>
        <div style={{ display: "flex", gap: 16 }}>
          <div style={{ flex: 1 }}>
            <label style={labelStyle}>服务器名称</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Server"
              style={{ width: "100%" }}
              autoFocus
            />
          </div>
          <div style={{ width: 160 }}>
            <label style={labelStyle}>类型</label>
            <select
              value={serverType}
              onChange={(e) => setServerType(e.target.value as ServerType)}
              style={{ width: "100%" }}
            >
              {SERVER_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* MC Version for Forge/NeoForge */}
      {NEEDS_MC_VERSION.includes(serverType) && (
        <div style={sectionStyle}>
          <label style={labelStyle}>Minecraft 版本</label>
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="筛选版本..."
            style={{ width: "100%", marginBottom: 8 }}
          />
          <div style={versionGrid}>
            {filteredVersions.slice(0, 60).map((v) => (
              <div
                key={v.id}
                onClick={() => { setMcVersion(v.id); setFilter(""); }}
                style={{
                  padding: "5px 10px", fontSize: 12, borderRadius: 3, cursor: "pointer",
                  background: mcVersion === v.id ? "var(--accent)" : "transparent",
                  color: mcVersion === v.id ? "#fff" : "var(--text-primary)",
                  transition: "background 0.1s", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                }}
              >
                {v.id}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sub-version for Forge/NeoForge */}
      {showSubSelector && (
        <div style={sectionStyle}>
          <label style={labelStyle}>
            {serverType} 版本{loadingSub && " — 加载中..."}
          </label>
          <div style={versionGrid}>
            {subVersions.map((v) => (
              <div
                key={v.id}
                onClick={() => setVersion(v.id)}
                style={{
                  padding: "5px 10px", fontSize: 12, borderRadius: 3, cursor: "pointer",
                  background: version === v.id ? "var(--accent)" : "transparent",
                  color: version === v.id ? "#fff" : "var(--text-primary)",
                  transition: "background 0.1s", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                }}
              >
                {v.id}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Single version selector */}
      {!NEEDS_MC_VERSION.includes(serverType) && (
        <div style={sectionStyle}>
          <label style={labelStyle}>版本</label>
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="筛选版本..."
            style={{ width: "100%", marginBottom: 8 }}
          />
          <div style={versionGrid}>
            {filteredVersions.slice(0, 60).map((v) => (
              <div
                key={v.id}
                onClick={() => { setVersion(v.id); setFilter(""); }}
                style={{
                  padding: "5px 10px", fontSize: 12, borderRadius: 3, cursor: "pointer",
                  background: version === v.id ? "var(--accent)" : "transparent",
                  color: version === v.id ? "#fff" : "var(--text-primary)",
                  transition: "background 0.1s", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                }}
              >
                {v.id}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Paper stability toggle */}
      {serverType === "Paper" && showSubSelector && (
        <div style={{ ...sectionStyle, marginBottom: 14 }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13, color: "var(--text-secondary)" }}>
            <input
              type="checkbox"
              checked={!stableOnly}
              onChange={(e) => setStableOnly(!e.target.checked)}
              style={{ cursor: "pointer" }}
            />
            允许非稳定版本
          </label>
        </div>
      )}

      {/* Memory & Java */}
      <div style={sectionStyle}>
        <div style={{ display: "flex", gap: 16 }}>
          <div style={{ flex: 1 }}>
            <label style={labelStyle}>最大内存 (MB)</label>
            <input
              type="number"
              value={maxMemory}
              onChange={(e) => setMaxMemory(Number(e.target.value))}
              style={{ width: "100%" }}
            />
          </div>
          <div style={{ flex: 1 }}>
            <label style={labelStyle}>Java 版本</label>
            <select
              value={javaVersion}
              onChange={(e) => {
                const v = e.target.value;
                setJavaVersion(v);
                setJavaWarning(Number(v) !== recommendedJava);
              }}
              style={{ width: "100%" }}
            >
              {["8", "11", "17", "21", "25"].map((j) => (
                <option key={j} value={j}>Java {j}</option>
              ))}
            </select>
            {javaWarning && (
              <p style={{ color: "var(--yellow)", fontSize: 11, marginTop: 4, marginBottom: 0, lineHeight: 1.4 }}>
                使用非推荐版本Java可能会无法启动服务器，后果自负
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Extra args */}
      <div style={sectionStyle}>
        <label style={labelStyle}>额外 JVM 参数</label>
        <input
          value={extraArgs}
          onChange={(e) => setExtraArgs(e.target.value)}
          placeholder="-Xms512M -XX:+UseG1GC"
          style={{ width: "100%" }}
        />
      </div>

      {error && (
        <p style={{ color: "var(--red)", fontSize: 13, marginBottom: 12 }}>{error}</p>
      )}

      <div style={{ display: "flex", gap: 12 }}>
        <button className="btn-primary" onClick={handleCreate} disabled={creating}>
          {creating ? "创建中..." : "安装服务器"}
        </button>
        <button className="btn-ghost" onClick={() => navigate("/")}>
          取消
        </button>
      </div>
    </div>
  );
}
