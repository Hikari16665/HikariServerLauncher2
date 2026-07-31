export type ServerType = "Vanilla" | "Paper" | "Forge" | "Fabric" | "NeoForge" | "April";

export interface Server {
  uuid: string;
  name: string;
  server_type: ServerType;
  max_memory: number;
  extra_args: string;
  path: string;
  java_version: string;
  valid: boolean;
}

export interface TaskInfo {
  task_id: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  progress_message: string;
  error_message: string | null;
  created_at: number;
  started_at: number | null;
  completed_at: number | null;
  result: Record<string, unknown> | null;
  title: string;
  current_step: string;
  steps: TaskStep[];
  metrics: TaskMetrics;
}

export interface TaskStep { id: string; label: string; status: "pending" | "running" | "completed" | "failed"; updated_at: number; }
export interface TaskMetrics { downloaded_bytes?: number; total_bytes?: number; speed_bps?: number; eta_seconds?: number; }

export interface ServerStatus {
  running: boolean;
  pid?: number;
  uptime?: number;
  command?: string;
}

export interface FileItem {
  name: string;
  path: string;
  type: "file" | "directory";
  size: number;
  modified: string;
}

export interface SpConfig {
  name: string;
  path: string;
  description: string;
  type: "properties" | "yml";
  keys: ConfigKey[];
}

export interface ConfigKey {
  name: string;
  key: string;
  description: string;
  tips: string;
  type: "int" | "bool" | "string" | "choice";
  current_value: string;
  danger: boolean;
  choices?: string[];
}

export interface BackupInfo {
  filename: string;
  server_uuid: string;
  size: number;
  created: string;
}

export interface VersionInfo {
  id: string;
  type: string;
  release_time: string;
}

export interface SystemStats {
  cpu_percent: number;
  mem_used_gb: number;
  mem_total_gb: number;
  mem_percent: number;
  net_sent_kbps: number;
  net_recv_kbps: number;
  disk_total_gb: number;
  disk_used_gb: number;
  timestamp: number;
}

export interface ServerDiskUsage {
  name: string;
  used_gb: number;
}

export interface DiskSnapshot {
  timestamp: number;
  disk_total_gb: number;
  disk_used_gb: number;
  server_usages?: ServerDiskUsage[];
}

export interface MarketProject { project_id: string; slug: string; title: string; description: string; author: string; icon_url?: string; categories: string[]; display_categories: string[]; versions: string[]; downloads: number; server_side: string; project_type: string; }
export interface MarketVersion { id: string; project_id: string; name: string; version_number: string; version_type: string; date_published: string; downloads: number; game_versions: string[]; loaders: string[]; files: { filename: string; url: string; primary: boolean; size: number }[]; dependencies: { version_id?: string; project_id?: string; dependency_type: string }[]; required_dependencies?: { project_id: string; title: string; description: string; icon_url?: string; categories: string[]; version: MarketVersion }[]; }
export interface InstalledAddon { filename: string; enabled: boolean; size: number; modified: number; name: string; version?: string; project_id?: string; version_id?: string; icon_url?: string; embedded_icon?: string; description?: string; }
export type DiagnosticLevel = "exception" | "severe_warning" | "warning" | "info";
export interface DiagnosticIssue { level: DiagnosticLevel; code: string; title: string; message: string; file?: string; details: Record<string, unknown>; }
export interface DiagnosticReport { server_uuid: string; server_name: string; checked_at: number; duration_ms: number; addon_count: number; healthy: boolean; summary: Record<DiagnosticLevel, number>; issues: DiagnosticIssue[]; }
