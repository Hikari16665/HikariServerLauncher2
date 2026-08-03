import { useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useNavigate } from "react-router-dom";
import { useSettings } from "../store/settings";
import { useToastStore } from "../store/toast";
import { api } from "../lib/api";

type PackFile = {
  key: string;
  path: string;
  size: number;
  env: string;
  id: string;
  title: string;
  description: string;
  icon_url?: string;
  categories: string[];
  version: string;
  supported: boolean;
  selected: boolean;
  reason: string;
};
type Manifest = {
  session_id: string;
  pack: {
    name: string;
    summary: string;
    version_id: string;
    minecraft: string;
    loader: { name: string; version: string; server_type: string };
  };
  files: PackFile[];
  rules_source: string;
};
type ProxyResponse = { status: number; body: string; error: string | null };

export default function ImportServer() {
  const navigate = useNavigate();
  const addToast = useToastStore((state) => state.addToast);
  const { apiUrl, token } = useSettings();
  const inputRef = useRef<HTMLInputElement>(null);
  const uploadingRef = useRef(false);
  const mountedRef = useRef(true);
  const inspectIdRef = useRef(0);
  const readerRef = useRef<FileReader | null>(null);
  const [stage, setStage] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [name, setName] = useState("");
  const [maxMemory, setMaxMemory] = useState(4096);
  const [javaVersion, setJavaVersion] = useState("Java 21");
  const [extraArgs, setExtraArgs] = useState("");
  const [files, setFiles] = useState<PackFile[]>([]);
  const [creating, setCreating] = useState(false);
  const [query, setQuery] = useState("");
  useEffect(() => {
    if (!manifest) return;
    api
      .get<{ recommended_java: number }>(
        `/api/versions/recommended-java?mc_version=${encodeURIComponent(manifest.pack.minecraft)}`,
      )
      .then((data) => setJavaVersion(`Java ${data.recommended_java}`))
      .catch(() => undefined);
  }, [manifest]);
  const visible = useMemo(
    () =>
      files.filter((item) =>
        `${item.title} ${item.id} ${item.description}`
          .toLowerCase()
          .includes(query.toLowerCase()),
      ),
    [files, query],
  );
  const selectedCount = files.filter((item) => item.selected).length;
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      inspectIdRef.current += 1;
      readerRef.current?.abort();
    };
  }, []);

  async function inspect(file?: File) {
    if (!file || uploadingRef.current) return;
    if (!file.name.toLowerCase().endsWith(".mrpack")) {
      addToast("请选择 .mrpack 文件", "error");
      return;
    }
    if (file.size > 512 * 1024 * 1024) {
      addToast("mrpack 文件不能超过 512 MB", "error");
      return;
    }
    const inspectId = ++inspectIdRef.current;
    uploadingRef.current = true;
    setUploading(true);
    try {
      const base64 = await fileToBase64(file, readerRef);
      if (inspectId !== inspectIdRef.current || !mountedRef.current) return;
      const response = await invoke<ProxyResponse>("proxy_upload", {
        req: {
          url: `${apiUrl}/api/mrpack/inspect`,
          file_data: base64,
          file_name: file.name,
          token: token || "",
        },
      });
      if (response.error) throw new Error(response.error);
      const body = JSON.parse(response.body || "{}");
      if (response.status < 200 || response.status >= 300)
        throw new Error(body.error || `HTTP ${response.status}`);
      if (inspectId !== inspectIdRef.current || !mountedRef.current) return;
      setManifest(body);
      setFiles(body.files);
      setName(body.pack.name);
      setStage(1);
    } catch (error: any) {
      if (
        inspectId === inspectIdRef.current &&
        mountedRef.current &&
        error?.name !== "AbortError"
      )
        addToast(error.message || "无法解析模组包", "error");
    } finally {
      if (inspectId === inspectIdRef.current) {
        uploadingRef.current = false;
        readerRef.current = null;
        if (mountedRef.current) setUploading(false);
      }
    }
  }

  function cancelInspect() {
    inspectIdRef.current += 1;
    readerRef.current?.abort();
    readerRef.current = null;
    uploadingRef.current = false;
    setUploading(false);
    setDragging(false);
    addToast("已停止读取模组包", "info");
  }

  function toggle(key: string) {
    setFiles((items) =>
      items.map((item) =>
        item.key === key && item.supported
          ? { ...item, selected: !item.selected }
          : item,
      ),
    );
  }
  function selectSupported(value: boolean) {
    setFiles((items) =>
      items.map((item) =>
        item.supported ? { ...item, selected: value } : item,
      ),
    );
  }
  async function create() {
    if (!manifest || !name.trim() || selectedCount === 0) return;
    setCreating(true);
    try {
      await api.post("/api/mrpack/import", {
        session_id: manifest.session_id,
        name: name.trim(),
        max_memory: maxMemory,
        java_version: javaVersion.replace("Java ", ""),
        extra_args: extraArgs,
        selected_paths: files
          .filter((item) => item.selected)
          .map((item) => item.path),
      });
      addToast(
        "模组包导入任务已创建",
        "success",
        `将安装 ${selectedCount} 个文件`,
      );
      navigate("/");
    } catch (error: any) {
      addToast(error.message || "无法创建导入任务", "error", error.detail);
    } finally {
      setCreating(false);
    }
  }

  return (
    <section className="page-shell mrpack-page">
      <header className="utility-header">
        <div>
          <h1>导入服务器</h1>
          <p>从 Modrinth .mrpack 创建专用服务器</p>
        </div>
        <div className="import-steps">
          <span className={stage >= 0 ? "active" : ""}>1 文件</span>
          <span className={stage >= 1 ? "active" : ""}>2 信息</span>
          <span className={stage >= 2 ? "active" : ""}>3 内容</span>
        </div>
      </header>
      {stage === 0 && (
        <div
          className={`mrpack-drop ${dragging ? "dragging" : ""} ${uploading ? "busy" : ""}`}
          onDragOver={(event) => {
            event.preventDefault();
            if (!uploadingRef.current) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            if (!uploadingRef.current) inspect(event.dataTransfer.files[0]);
          }}
          onClick={() => {
            if (!uploadingRef.current) inputRef.current?.click();
          }}
        >
          <input
            ref={inputRef}
            hidden
            disabled={uploading}
            type="file"
            accept=".mrpack,application/x-modrinth-modpack+zip"
            onChange={(event) => {
              const file = event.target.files?.[0];
              event.target.value = "";
              inspect(file);
            }}
          />
          <span>⇩</span>
          <strong>{uploading ? "正在读取模组包…" : "拖入 .mrpack 文件"}</strong>
          <p>
            {uploading
              ? "正在解析文件和模组元数据。"
              : "或者点击选择文件。解析过程不会修改现有服务器。"}
          </p>
        </div>
      )}
      {uploading && (
        <div className="mrpack-reading-lock" role="status" aria-live="polite">
          <div>
            <span className="loading-spinner" />
            <strong>正在读取模组包</strong>
            <p>正在上传并分析模组信息，可以取消或切换到其他页面。</p>
            <button className="btn-ghost" onClick={cancelInspect}>
              取消读取
            </button>
          </div>
        </div>
      )}
      {stage === 1 && manifest && (
        <div className="mrpack-meta-layout">
          <main className="surface mrpack-meta">
            <div className="pack-heading">
              <div>
                <span>MODRINTH MODPACK</span>
                <h2>{manifest.pack.name}</h2>
                <p>{manifest.pack.summary || "该模组包没有提供简介。"}</p>
              </div>
              <dl>
                <div>
                  <dt>Minecraft</dt>
                  <dd>{manifest.pack.minecraft}</dd>
                </div>
                <div>
                  <dt>加载器</dt>
                  <dd>
                    {manifest.pack.loader.server_type}{" "}
                    {manifest.pack.loader.version}
                  </dd>
                </div>
                <div>
                  <dt>声明文件</dt>
                  <dd>{manifest.files.length}</dd>
                </div>
              </dl>
            </div>
            <div className="form-grid form-grid-name">
              <label>
                服务器名称
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
              </label>
              <label>
                最大内存（MB）
                <input
                  type="number"
                  min="1024"
                  step="512"
                  value={maxMemory}
                  onChange={(event) => setMaxMemory(Number(event.target.value))}
                />
              </label>
              <label>
                Java 版本
                <select
                  value={javaVersion}
                  onChange={(event) => setJavaVersion(event.target.value)}
                >
                  {["8", "11", "17", "21", "25"].map((item) => (
                    <option key={item}>Java {item}</option>
                  ))}
                </select>
              </label>
              <label>
                额外 JVM 参数
                <input
                  value={extraArgs}
                  onChange={(event) => setExtraArgs(event.target.value)}
                  placeholder="-Xms1G"
                />
              </label>
            </div>
          </main>
          <aside className="surface mrpack-next">
            <strong>下一步将选择服务端内容</strong>
            <p>客户端专用模组和云端不兼容规则命中的项目会默认取消并锁定。</p>
            <button
              className="btn-primary"
              disabled={!name.trim()}
              onClick={() => setStage(2)}
            >
              检查模组列表
            </button>
            <button className="btn-ghost" onClick={() => setStage(0)}>
              重新选择文件
            </button>
          </aside>
        </div>
      )}
      {stage === 2 && manifest && (
        <div className="mrpack-content">
          <div className="mrpack-toolbar">
            <div>
              <strong>
                {selectedCount} / {files.length} 项将安装
              </strong>
              <span>
                Minecraft {manifest.pack.minecraft} ·{" "}
                {manifest.pack.loader.server_type} · 规则：
                {manifest.rules_source}
              </span>
            </div>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="筛选名称或 ID…"
            />
            <button className="btn-ghost" onClick={() => selectSupported(true)}>
              全选兼容项
            </button>
            <button
              className="btn-ghost"
              onClick={() => selectSupported(false)}
            >
              清空
            </button>
          </div>
          <div className="mrpack-card-grid">
            {visible.map((item) => (
              <article
                key={item.key}
                className={`mrpack-card ${!item.supported ? "unsupported" : ""}`}
                onClick={() => toggle(item.key)}
              >
                <input
                  type="checkbox"
                  checked={item.selected}
                  disabled={!item.supported}
                  onChange={() => toggle(item.key)}
                  onClick={(event) => event.stopPropagation()}
                />
                {item.icon_url ? (
                  <img src={item.icon_url} alt="" />
                ) : (
                  <span className="mrpack-placeholder">◇</span>
                )}
                <div>
                  <div className="mrpack-card-title">
                    <strong>{item.title}</strong>
                    <code>{item.version || item.id}</code>
                  </div>
                  <p>{item.description}</p>
                  <small>
                    {item.path} · {formatBytes(item.size)}
                  </small>
                  <span className="category-tags">
                    {item.categories.slice(0, 3).map((tag) => (
                      <i key={tag}>{tag}</i>
                    ))}
                  </span>
                </div>
              </article>
            ))}
          </div>
          <footer className="mrpack-actions">
            <button className="btn-ghost" onClick={() => setStage(1)}>
              返回修改信息
            </button>
            <button
              className="btn-primary"
              disabled={creating || selectedCount === 0}
              onClick={create}
            >
              {creating ? "正在创建任务…" : `导入服务器（${selectedCount} 项）`}
            </button>
          </footer>
        </div>
      )}
    </section>
  );
}

function fileToBase64(
  file: File,
  readerRef: React.MutableRefObject<FileReader | null>,
): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    readerRef.current = reader;
    reader.onload = () => resolve(String(reader.result).split(",")[1]);
    reader.onerror = () => reject(reader.error || new Error("读取文件失败"));
    reader.onabort = () => reject(new DOMException("读取已取消", "AbortError"));
    reader.readAsDataURL(file);
  });
}
function formatBytes(value: number) {
  if (!value) return "未知大小";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), 3);
  return `${(value / 1024 ** index).toFixed(index ? 1 : 0)} ${units[index]}`;
}
