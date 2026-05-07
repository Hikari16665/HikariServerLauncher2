import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { api, ApiError } from "../lib/api";
import type { VersionInfo, ServerType } from "../lib/types";
import { useTaskStore } from "../store/tasks";
import { useToastStore } from "../store/toast";

const SERVER_TYPES: ServerType[] = [
  "Vanilla",
  "Paper",
  "Forge",
  "Fabric",
  "NeoForge",
  "April",
];

const NEEDS_MC_VERSION: ServerType[] = ["Forge", "NeoForge"];

function mapVersions(type: ServerType, data: any): VersionInfo[] {
  switch (type) {
    case "Vanilla":
      return (data.releases || []).map((v: any) => ({
        id: v.id,
        type: v.type || "release",
        release_time: v.release_time || "",
      }));
    case "Paper":
      return (data.latest_version_builds || []).map((b: any) => ({
        id: `${b.version}-build${b.build}`,
        type: b.channel || "release",
        release_time: "",
      }));
    case "Forge":
      return (data.mc_versions || data.forge_versions || []).map((v: string) => ({
        id: v,
        type: "release",
        release_time: "",
      }));
    case "NeoForge":
      return (data.mc_versions || data.neoforge_versions || []).map((v: string) => ({
        id: v,
        type: "release",
        release_time: "",
      }));
    case "Fabric":
      return (data.mc_versions || []).map((v: any) => ({
        id: v.version || v,
        type: "release",
        release_time: "",
      }));
    case "April":
      return (data.versions || []).map((v: any) => ({
        id: v.name || v.version,
        type: "release",
        release_time: "",
      }));
    default:
      return [];
  }
}

function mapSubVersions(type: ServerType, data: any): VersionInfo[] {
  switch (type) {
    case "Forge":
      return (data.forge_versions || []).map((v: any) => ({
        id: v.version,
        type: "release",
        release_time: data.mc_version || "",
      }));
    case "NeoForge":
      return (data.neoforge_versions || []).map((v: any) => ({
        id: typeof v === "string" ? v : v.version || v.name || "",
        type: "release",
        release_time: data.mc_version || "",
      }));
    default:
      return [];
  }
}

export default function CreateServer() {
  const [name, setName] = useState("");
  const [serverType, setServerType] = useState<ServerType>("Vanilla");
  const [version, setVersion] = useState("");
  const [mcVersion, setMcVersion] = useState("");
  const [versions, setVersions] = useState<VersionInfo[]>([]);
  const [subVersions, setSubVersions] = useState<VersionInfo[]>([]);
  const [maxMemory, setMaxMemory] = useState(2048);
  const [javaVersion, setJavaVersion] = useState("21");
  const [extraArgs, setExtraArgs] = useState("");
  const [filter, setFilter] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [loadingSub, setLoadingSub] = useState(false);

  const navigate = useNavigate();
  const setTasks = useTaskStore((s) => s.setTasks);
  const addToast = useToastStore((s) => s.addToast);

  // Load top-level versions when server type changes
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

  // Load sub-versions when mcVersion changes (Forge/NeoForge)
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
        if (mapped.length > 0) {
          setVersion(mapped[0].id);
        }
      })
      .catch((e) => {
        addToast("加载版本列表失败", "error", String(e));
        setSubVersions([]);
      })
      .finally(() => setLoadingSub(false));
  }, [mcVersion, serverType]);

  async function handleCreate() {
    if (!name.trim()) {
      setError("请输入服务器名称");
      return;
    }
    if (!version) {
      setError("请选择版本");
      return;
    }
    // For Forge/NeoForge, require mcVersion
    if (NEEDS_MC_VERSION.includes(serverType) && !mcVersion) {
      setError("请选择 Minecraft 版本");
      return;
    }
    setCreating(true);
    setError("");

    // Build final version string
    const finalVersion =
      NEEDS_MC_VERSION.includes(serverType) && mcVersion
        ? `${mcVersion}|${version}`
        : version;

    try {
      await api.post<{ task_id: string }>("/api/servers/create", {
        name: name.trim(),
        server_type: serverType,
        version: finalVersion,
        max_memory: maxMemory,
        java_version: javaVersion,
        extra_args: extraArgs,
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

  // Show sub-version selector for Forge/NeoForge
  const showSubSelector =
    NEEDS_MC_VERSION.includes(serverType) && mcVersion;

  return (
    <div style={{ padding: 24, maxWidth: 700, margin: "0 auto", width: "100%" }}>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1
          style={{
            fontSize: 20,
            fontWeight: 600,
            marginBottom: 24,
          }}
        >
          创建服务器
        </h1>

        {/* Name & Type row */}
        <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
          <div style={{ flex: 1 }}>
            <label
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "var(--text-secondary)",
                display: "block",
                marginBottom: 6,
              }}
            >
              服务器名称
            </label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Server"
              style={{ width: "100%" }}
              autoFocus
            />
          </div>
          <div style={{ width: 160 }}>
            <label
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "var(--text-secondary)",
                display: "block",
                marginBottom: 6,
              }}
            >
              类型
            </label>
            <select
              value={serverType}
              onChange={(e) => setServerType(e.target.value as ServerType)}
              style={{ width: "100%" }}
            >
              {SERVER_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* MC Version selector (Forge/NeoForge) */}
        {NEEDS_MC_VERSION.includes(serverType) && (
          <div style={{ marginBottom: 16 }}>
            <label
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "var(--text-secondary)",
                display: "block",
                marginBottom: 6,
              }}
            >
              Minecraft 版本
            </label>
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="筛选版本..."
              style={{ width: "100%", marginBottom: 8 }}
            />
            <div
              style={{
                maxHeight: 120,
                overflow: "auto",
                background: "var(--bg-secondary)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-sm)",
                padding: 4,
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))",
                gap: 4,
              }}
            >
              {filteredVersions.slice(0, 60).map((v) => (
                <div
                  key={v.id}
                  onClick={() => { setMcVersion(v.id); setFilter(""); }}
                  style={{
                    padding: "6px 10px",
                    fontSize: 12,
                    borderRadius: 3,
                    cursor: "pointer",
                    background:
                      mcVersion === v.id
                        ? "var(--accent)"
                        : "transparent",
                    color:
                      mcVersion === v.id ? "#fff" : "var(--text-primary)",
                    transition: "background 0.1s",
                  }}
                >
                  {v.id}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Sub-version selector (Forge version / Fabric) */}
        {showSubSelector && (
          <div style={{ marginBottom: 16 }}>
            <label
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "var(--text-secondary)",
                display: "block",
                marginBottom: 6,
              }}
            >
              {serverType} 版本
              {loadingSub && " — 加载中..."}
            </label>
            <div
              style={{
                maxHeight: 160,
                overflow: "auto",
                background: "var(--bg-secondary)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-sm)",
                padding: 4,
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
                gap: 4,
              }}
            >
              {subVersions.map((v) => (
                <div
                  key={v.id}
                  onClick={() => setVersion(v.id)}
                  style={{
                    padding: "6px 10px",
                    fontSize: 12,
                    borderRadius: 3,
                    cursor: "pointer",
                    background:
                      version === v.id
                        ? "var(--accent)"
                        : "transparent",
                    color:
                      version === v.id ? "#fff" : "var(--text-primary)",
                    transition: "background 0.1s",
                  }}
                >
                  {v.id}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Single version selector (Vanilla/Paper/April) */}
        {!NEEDS_MC_VERSION.includes(serverType) && (
          <div style={{ marginBottom: 16 }}>
            <label
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "var(--text-secondary)",
                display: "block",
                marginBottom: 6,
              }}
            >
              版本
            </label>
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="筛选版本..."
              style={{ width: "100%", marginBottom: 8 }}
            />
            <div
              style={{
                maxHeight: 180,
                overflow: "auto",
                background: "var(--bg-secondary)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-sm)",
                padding: 4,
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))",
                gap: 4,
              }}
            >
              {filteredVersions.slice(0, 60).map((v) => (
                <div
                  key={v.id}
                  onClick={() => { setVersion(v.id); setFilter(""); }}
                  style={{
                    padding: "6px 10px",
                    fontSize: 12,
                    borderRadius: 3,
                    cursor: "pointer",
                    background:
                      version === v.id
                        ? "var(--accent)"
                        : "transparent",
                    color:
                      version === v.id ? "#fff" : "var(--text-primary)",
                    transition: "background 0.1s",
                  }}
                >
                  {v.id}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Memory & Java */}
        <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
          <div style={{ flex: 1 }}>
            <label
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "var(--text-secondary)",
                display: "block",
                marginBottom: 6,
              }}
            >
              最大内存 (MB)
            </label>
            <input
              type="number"
              value={maxMemory}
              onChange={(e) => setMaxMemory(Number(e.target.value))}
              style={{ width: "100%" }}
            />
          </div>
          <div style={{ flex: 1 }}>
            <label
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "var(--text-secondary)",
                display: "block",
                marginBottom: 6,
              }}
            >
              Java 版本
            </label>
            <select
              value={javaVersion}
              onChange={(e) => setJavaVersion(e.target.value)}
              style={{ width: "100%" }}
            >
              {["8", "11", "17", "21"].map((j) => (
                <option key={j} value={j}>
                  Java {j}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Extra args */}
        <div style={{ marginBottom: 24 }}>
          <label
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: "var(--text-secondary)",
              display: "block",
              marginBottom: 6,
            }}
          >
            额外 JVM 参数
          </label>
          <input
            value={extraArgs}
            onChange={(e) => setExtraArgs(e.target.value)}
            placeholder="-Xms512M -XX:+UseG1GC"
            style={{ width: "100%" }}
          />
        </div>

        {error && (
          <motion.p
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            style={{
              color: "var(--red)",
              fontSize: 13,
              marginBottom: 12,
            }}
          >
            {error}
          </motion.p>
        )}

        <div style={{ display: "flex", gap: 12 }}>
          <button
            className="btn-primary"
            onClick={handleCreate}
            disabled={creating}
          >
            {creating ? "创建中..." : "创建服务器"}
          </button>
          <button className="btn-ghost" onClick={() => navigate("/")}>
            取消
          </button>
        </div>
      </motion.div>
    </div>
  );
}
