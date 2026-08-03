import { useEffect, useState, useCallback, useRef } from "react";
import { motion } from "framer-motion";
import { invoke } from "@tauri-apps/api/core";
import { api } from "../lib/api";
import type { FileItem } from "../lib/types";
import { useSettings } from "../store/settings";
import { useToastStore } from "../store/toast";
import { showConfirm } from "./ConfirmDialog";

interface Props {
  serverUuid: string;
}

export default function FileBrowser({ serverUuid }: Props) {
  const [path, setPath] = useState("");
  const [files, setFiles] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingFile, setEditingFile] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const [savingFile, setSavingFile] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(false);
  const apiUrl = useSettings((s) => s.apiUrl);
  const token = useSettings((s) => s.token);
  const addToast = useToastStore((s) => s.addToast);
  const uploadRef = useRef<HTMLInputElement>(null);

  const fetchFiles = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<{ items: FileItem[]; path: string }>(
        `/api/servers/${serverUuid}/files?path=${encodeURIComponent(path)}`
      );
      setFiles(data.items || []);
    } catch (e: any) {
      addToast(e.message || "加载文件列表失败", "error", e.detail);
      setFiles([]);
    } finally {
      setLoading(false);
    }
  }, [serverUuid, path]);

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  async function handleDelete(file: FileItem) {
    if (!(await showConfirm(`确定删除 ${file.name}？`))) return;
    try {
      await api.delete(
        `/api/servers/${serverUuid}/files?path=${encodeURIComponent(file.path)}`
      );
      fetchFiles();
    } catch (e: any) {
      addToast(e.message || "删除失败", "error", e.detail);
    }
  }

  async function handleDownload(file: FileItem) {
    if (file.type === "directory") return;
    window.open(
      `${apiUrl}/api/servers/${serverUuid}/files/download?path=${encodeURIComponent(file.path)}&token=${token}`
    );
  }

  async function handleEdit(file: FileItem) {
    if (file.type === "directory") return;
    if (file.size > 1024 * 1024) {
      addToast("文件过大，无法在线编辑", "info");
      return;
    }
    try {
      const data = await api.get<{ content: string }>(
        `/api/servers/${serverUuid}/files/read?path=${encodeURIComponent(file.path)}`
      );
      setEditingFile(file.path);
      setEditContent(data.content);
    } catch (e: any) {
      addToast(e.message || "读取失败", "error", e.detail);
    }
  }

  async function handleSaveEdit() {
    if (!editingFile) return;
    setSavingFile(true);
    try {
      await api.put(
        `/api/servers/${serverUuid}/files`,
        { path: editingFile, content: editContent }
      );
      setEditingFile(null);
      setEditContent("");
      fetchFiles();
    } catch (e: any) {
      addToast(e.message || "保存失败", "error", e.detail);
    } finally {
      setSavingFile(false);
    }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 512 * 1024 * 1024) {
      addToast("文件不能超过 512 MB", "error");
      e.target.value = "";
      return;
    }

    setUploadingFile(true);
    try {
      const base64 = await fileToBase64(file);
      const url = `${apiUrl}/api/servers/${serverUuid}/files/upload?path=${encodeURIComponent(path)}`;
      const resp = await invoke<{ status: number; body: string; error: string | null }>("proxy_upload", {
        req: { url, file_data: base64, file_name: file.name, token: token || "" },
      });
      if (resp.error) {
        throw { message: resp.error, detail: `上传到 ${url}\n${resp.error}` };
      }
      if (resp.status < 200 || resp.status >= 300) {
        let msg = `HTTP ${resp.status}`;
        try { const b = JSON.parse(resp.body); if (b.error) msg = b.error; } catch {}
        throw { message: msg, detail: `上传到 ${url}\n状态: ${resp.status}\n响应: ${resp.body.slice(0, 300)}` };
      }
      fetchFiles();
      addToast("上传成功", "success");
    } catch (e: any) {
      addToast(e.message || "上传失败", "error", e.detail);
    } finally {
      setUploadingFile(false);
      if (uploadRef.current) uploadRef.current.value = "";
    }
  }

  const parentPath = path.includes("/")
    ? path.slice(0, path.lastIndexOf("/"))
    : "";

  // File edit modal
  if (editingFile) {
    return (
      <div style={{ height: "100%", display: "flex", flexDirection: "column", padding: 16 }}>
        <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 12 }}>
          <span style={{ fontSize: 13, fontWeight: 600, flex: 1 }}>
            编辑: {editingFile}
          </span>
          <button className="btn-primary" onClick={handleSaveEdit} disabled={savingFile} style={{ fontSize: 12 }}>
            {savingFile ? "保存中..." : "保存"}
          </button>
          <button className="btn-ghost" onClick={() => { setEditingFile(null); setEditContent(""); }} style={{ fontSize: 12 }}>
            取消
          </button>
        </div>
        <textarea
          value={editContent}
          onChange={(e) => setEditContent(e.target.value)}
          style={{
            flex: 1,
            fontFamily: "var(--mono)",
            fontSize: 12,
            resize: "none",
            background: "var(--bg-primary)",
            color: "var(--text-primary)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-sm)",
            padding: 12,
          }}
        />
      </div>
    );
  }

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      {/* Toolbar */}
      <div style={{ display: "flex", gap: 8, padding: "10px 16px", borderBottom: "1px solid var(--border)", alignItems: "center", flexShrink: 0 }}>
        <input
          value={path || "/"}
          onChange={(e) => setPath(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && fetchFiles()}
          style={{ flex: 1, fontSize: 12, padding: "4px 8px" }}
        />
        <button className="btn-ghost" onClick={() => fetchFiles()} style={{ fontSize: 12 }}>刷新</button>
        <button className="btn-ghost" disabled={uploadingFile} onClick={() => uploadRef.current?.click()} style={{ fontSize: 12 }}>
          {uploadingFile ? "正在上传…" : "上传"}
        </button>
        <input ref={uploadRef} type="file" onChange={handleUpload} style={{ display: "none" }} />
      </div>

      {/* File list */}
      <div style={{ flex: 1, overflow: "auto", padding: "8px 12px" }}>
        {loading ? (
          <div style={{ textAlign: "center", padding: 32, color: "var(--text-muted)", fontSize: 13 }}>加载中...</div>
        ) : (
          <>
            {/* Parent directory */}
            {path && (
              <div
                onClick={() => setPath(parentPath)}
                style={{
                  padding: "8px 10px",
                  cursor: "pointer",
                  borderRadius: "var(--radius-sm)",
                  fontSize: 13,
                  color: "var(--accent)",
                  fontWeight: 500,
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  marginBottom: 4,
                  transition: "background 0.1s",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-tertiary)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                📁 ..
              </div>
            )}

            {files
              .slice()
              .sort((a, b) => {
                if (a.type !== b.type) return a.type === "directory" ? -1 : 1;
                return a.name.localeCompare(b.name);
              })
              .map((f) => (
                <motion.div
                  key={f.path}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  style={{
                    padding: "8px 10px",
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    borderRadius: "var(--radius-sm)",
                    cursor: "pointer",
                    fontSize: 13,
                    transition: "background 0.1s",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-tertiary)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  onDoubleClick={() => {
                    if (f.type === "directory") setPath(f.path);
                  }}
                >
                  <span style={{ flexShrink: 0 }}>
                    {f.type === "directory" ? "📁" : "📄"}
                  </span>
                  <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {f.name}
                  </span>
                  <span style={{ fontSize: 11, color: "var(--text-muted)", flexShrink: 0 }}>
                    {formatSize(f.size)}
                  </span>
                  <div style={{ display: "flex", gap: 4, flexShrink: 0 }} onClick={(e) => e.stopPropagation()}>
                    <button
                      className="btn-ghost"
                      style={{ fontSize: 10, padding: "2px 6px" }}
                      onClick={() => handleEdit(f)}
                    >
                      编辑
                    </button>
                    <button
                      className="btn-ghost"
                      style={{ fontSize: 10, padding: "2px 6px" }}
                      onClick={() => handleDownload(f)}
                    >
                      下载
                    </button>
                    <button
                      className="btn-ghost"
                      style={{ fontSize: 10, padding: "2px 6px", color: "var(--red)" }}
                      onClick={() => handleDelete(f)}
                    >
                      删除
                    </button>
                  </div>
                </motion.div>
              ))}
          </>
        )}
      </div>
    </div>
  );
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // Remove data URL prefix
      const base64 = result.split(",")[1];
      resolve(base64);
    };
    reader.onerror = () => reject(new Error("读取文件失败"));
    reader.readAsDataURL(file);
  });
}

function formatSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}
