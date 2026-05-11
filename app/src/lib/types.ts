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
}

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

export interface DiskSnapshot {
  timestamp: number;
  disk_total_gb: number;
  disk_used_gb: number;
}
