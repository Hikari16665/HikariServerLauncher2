import { useEffect, useState, useCallback } from "react";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { api } from "../lib/api";
import type { SystemStats, DiskSnapshot, ServerDiskUsage } from "../lib/types";

const MAX_POINTS = 60;

interface CpuPoint {
  time: string;
  cpu: number;
}
interface MemPoint {
  time: string;
  used: number;
  total: number;
}
interface NetPoint {
  time: string;
  sent: number;
  recv: number;
}
interface DiskPoint {
  time: string;
  total: number;
  servers: ServerDiskUsage[];
}

// Module-level ring buffers — survive page navigation
const cpuBuf: CpuPoint[] = [];
const memBuf: MemPoint[] = [];
const netBuf: NetPoint[] = [];
let lastDiskFetch = 0;
let cachedDiskData: DiskPoint[] = [];

function formatTime(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatGB(v: number): string {
  return v.toFixed(1) + " GB";
}

export default function Dashboard() {
  const [cpuData, setCpuData] = useState<CpuPoint[]>(cpuBuf);
  const [memData, setMemData] = useState<MemPoint[]>(memBuf);
  const [netData, setNetData] = useState<NetPoint[]>(netBuf);
  const [diskData, setDiskData] = useState<DiskPoint[]>(cachedDiskData);
  const [error, setError] = useState<string | null>(null);
  const [diskError, setDiskError] = useState(false);

  const pushStats = useCallback((stats: SystemStats) => {
    const t = formatTime(stats.timestamp);

    cpuBuf.push({ time: t, cpu: stats.cpu_percent });
    if (cpuBuf.length > MAX_POINTS) cpuBuf.shift();
    setCpuData([...cpuBuf]);

    memBuf.push({ time: t, used: stats.mem_used_gb, total: stats.mem_total_gb });
    if (memBuf.length > MAX_POINTS) memBuf.shift();
    setMemData([...memBuf]);

    netBuf.push({ time: t, sent: stats.net_sent_kbps, recv: stats.net_recv_kbps });
    if (netBuf.length > MAX_POINTS) netBuf.shift();
    setNetData([...netBuf]);
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const stats = await api.get<SystemStats>("/api/system/stats");
      pushStats(stats);
      setError(null);
    } catch (e: any) {
      setError(e.message || "获取系统状态失败");
    }
  }, [pushStats]);

  const fetchDiskHistory = useCallback(async () => {
    const now = Date.now();
    if (now - lastDiskFetch < 30000) return;
    lastDiskFetch = now;
    try {
      const resp = await api.get<{ history: DiskSnapshot[] }>(
        "/api/system/disk-history"
      );
      cachedDiskData = resp.history.map((s) => ({
        time: formatTime(s.timestamp),
        total: s.disk_total_gb,
        servers: s.server_usages || [],
      }));
      setDiskData(cachedDiskData);
      setDiskError(false);
    } catch {
      setDiskError(true);
    }
  }, []);

  useEffect(() => {
    fetchStats();
    fetchDiskHistory();
    const statsTimer = setInterval(fetchStats, 4000);
    const diskTimer = setInterval(fetchDiskHistory, 60000);
    return () => {
      clearInterval(statsTimer);
      clearInterval(diskTimer);
    };
  }, [fetchStats, fetchDiskHistory]);

  const card: React.CSSProperties = {
    background: "var(--bg-secondary)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    padding: "14px 16px 16px",
  };

  const cardTitle: React.CSSProperties = {
    fontSize: 12,
    fontWeight: 600,
    color: "var(--text-primary)",
    marginBottom: 12,
  };

  const tooltipStyle = {
    contentStyle: {
      background: "var(--bg-primary)",
      border: "1px solid var(--border)",
      borderRadius: 6,
      fontSize: 12,
      fontFamily: "var(--font)",
    },
  };

  return (
    <section className="page-shell dashboard-page">
      <header className="page-header"><div><span className="page-kicker">OVERVIEW</span><h1>系统概览</h1><p>主机资源与服务器磁盘用量</p></div></header>

      {error && (
        <div
          style={{
            padding: "7px 12px",
            marginBottom: 14,
            background: "var(--red-bg)",
            color: "var(--red)",
            borderRadius: "var(--radius-sm)",
            fontSize: 12,
            fontWeight: 500,
          }}
        >
          {error}
        </div>
      )}

      <div className="dashboard-grid"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, 1fr)",
          gap: 14,
        }}
      >
        {/* CPU */}
        <div style={card}>
          <div style={cardTitle}>CPU 使用率</div>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={cpuData.slice()}>
              <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" strokeOpacity={0.5} />
              <XAxis dataKey="time" stroke="var(--text-muted)" fontSize={10} interval="preserveStartEnd" />
              <YAxis stroke="var(--text-muted)" fontSize={10} domain={[0, 100]} unit="%" />
              <Tooltip {...tooltipStyle} />
              <Line
                type="monotone"
                dataKey="cpu"
                stroke="var(--accent)"
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Memory */}
        <div style={card}>
          <div style={cardTitle}>内存</div>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={memData.slice()}>
              <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" strokeOpacity={0.5} />
              <XAxis dataKey="time" stroke="var(--text-muted)" fontSize={10} interval="preserveStartEnd" />
              <YAxis stroke="var(--text-muted)" fontSize={10} tickFormatter={formatGB} />
              <Tooltip {...tooltipStyle} formatter={(v) => [formatGB(Number(v))]} />
              <Line
                type="monotone"
                dataKey="used"
                stroke="var(--accent)"
                strokeWidth={1.5}
                dot={false}
                name="已用"
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="total"
                stroke="var(--text-muted)"
                strokeWidth={1.5}
                strokeDasharray="4 4"
                dot={false}
                name="总量"
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Network */}
        <div style={card}>
          <div style={cardTitle}>网络 IO</div>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={netData.slice()}>
              <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" strokeOpacity={0.5} />
              <XAxis dataKey="time" stroke="var(--text-muted)" fontSize={10} interval="preserveStartEnd" />
              <YAxis stroke="var(--text-muted)" fontSize={10} unit=" KB/s" />
              <Tooltip {...tooltipStyle} />
              <Line
                type="monotone"
                dataKey="sent"
                stroke="var(--accent)"
                strokeWidth={1.5}
                dot={false}
                name="发送"
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="recv"
                stroke="var(--green)"
                strokeWidth={1.5}
                dot={false}
                name="接收"
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Disk stacked area */}
        <div style={card}>
          <div style={cardTitle}>
            服务器硬盘用量
            {diskData.length === 0 && (
              <span style={{ fontSize: 10, color: "var(--text-muted)", marginLeft: 8, textTransform: "none", letterSpacing: 0 }}>
                {diskError ? "磁盘历史加载失败" : "暂无历史数据"}
              </span>
            )}
          </div>
          {diskData.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={diskData.slice()}>
                <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" strokeOpacity={0.5} />
                <XAxis dataKey="time" stroke="var(--text-muted)" fontSize={10} interval="preserveStartEnd" />
                <YAxis stroke="var(--text-muted)" fontSize={10} tickFormatter={formatGB} />
                <Tooltip {...tooltipStyle} formatter={(v) => [formatGB(Number(v))]} />
                {diskData[0]?.servers.map((s, i) => {
                  const colors = ["var(--accent)", "var(--green)", "var(--yellow)", "#a371f7", "#ff7b72", "#56d4dd"];
                  const c = colors[i % colors.length];
                  return (
                    <Area
                      key={s.name}
                      type="monotone"
                      dataKey={(pt: DiskPoint) => pt.servers[i]?.used_gb ?? 0}
                      stackId="1"
                      stroke={c}
                      fill={c}
                      fillOpacity={0.3}
                      name={s.name}
                      isAnimationActive={false}
                    />
                  );
                })}
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div
              style={{
                height: 180,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--text-muted)",
                fontSize: 12,
              }}
            >
              {diskError ? "无法读取磁盘历史，请检查后端连接" : "等待数据采集..."}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
