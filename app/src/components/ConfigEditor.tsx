import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api } from "../lib/api";
import type { SpConfig, ConfigKey } from "../lib/types";
import { useToastStore } from "../store/toast";

interface Props {
  serverUuid: string;
}

export default function ConfigEditor({ serverUuid }: Props) {
  const [configs, setConfigs] = useState<SpConfig[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [edited, setEdited] = useState<Set<string>>(new Set());
  const addToast = useToastStore((s) => s.addToast);

  useEffect(() => {
    api
      .get<{ configs: SpConfig[] }>(`/api/servers/${serverUuid}/spconfigs`)
      .then((d) => {
        setConfigs(d.configs);
        if (d.configs.length > 0) {
          setSelected(d.configs[0].path);
          const vals: Record<string, string> = {};
          for (const cfg of d.configs) {
            for (const k of cfg.keys) {
              vals[`${cfg.path}::${k.key}`] = k.current_value;
            }
          }
          setValues(vals);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [serverUuid]);

  async function handleSave(cfg: SpConfig) {
    setSaving(cfg.path);
    try {
      for (const k of cfg.keys) {
        const vkey = `${cfg.path}::${k.key}`;
        if (edited.has(vkey)) {
          await api.put(
            `/api/servers/${serverUuid}/spconfigs/${encodeURIComponent(cfg.path)}`,
            { key: k.key, value: values[vkey] || "" }
          );
        }
      }
      setEdited(new Set());
    } catch (e: any) {
      addToast(e.message || "保存失败", "error", e.detail);
    } finally {
      setSaving(null);
    }
  }

  function renderInput(k: ConfigKey) {
    const vkey = `${selected}::${k.key}`;
    const val = values[vkey] || "";

    if (k.type === "bool") {
      return (
        <div
          onClick={() => {
            setValues({ ...values, [vkey]: val === "true" ? "false" : "true" });
            setEdited(new Set([...edited, vkey]));
          }}
          style={{
            width: 40,
            height: 22,
            borderRadius: 11,
            background: val === "true" ? "var(--green)" : "var(--border)",
            position: "relative",
            cursor: "pointer",
            transition: "background 0.2s",
            flexShrink: 0,
          }}
        >
          <motion.div
            animate={{ x: val === "true" ? 20 : 2 }}
            style={{
              width: 18,
              height: 18,
              borderRadius: 9,
              background: "#fff",
              position: "absolute",
              top: 2,
            }}
          />
        </div>
      );
    }

    if (k.type === "choice" && k.choices) {
      return (
        <select
          value={val}
          onChange={(e) => {
            setValues({ ...values, [vkey]: e.target.value });
            setEdited(new Set([...edited, vkey]));
          }}
          style={{ minWidth: 160, fontSize: 12 }}
        >
          {k.choices.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      );
    }

    return (
      <input
        type={k.type === "int" ? "number" : "text"}
        value={val}
        onChange={(e) => {
          setValues({ ...values, [vkey]: e.target.value });
          setEdited(new Set([...edited, vkey]));
        }}
        style={{ minWidth: 160, fontSize: 12 }}
      />
    );
  }

  if (loading) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          color: "var(--text-muted)",
        }}
      >
        加载中...
      </div>
    );
  }

  if (configs.length === 0) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          color: "var(--text-muted)",
        }}
      >
        无配置文件
      </div>
    );
  }

  const currentCfg = configs.find((c) => c.path === selected);

  return (
    <div style={{ height: "100%", display: "flex", overflow: "hidden" }}>
      {/* Config file list sidebar */}
      <div
        style={{
          width: 180,
          borderRight: "1px solid var(--border)",
          padding: "8px 0",
          overflow: "auto",
          flexShrink: 0,
        }}
      >
        {configs.map((cfg) => (
          <div
            key={cfg.path}
            onClick={() => setSelected(cfg.path)}
            style={{
              padding: "8px 16px",
              fontSize: 13,
              cursor: "pointer",
              color:
                selected === cfg.path
                  ? "var(--accent)"
                  : "var(--text-secondary)",
              background:
                selected === cfg.path ? "var(--bg-tertiary)" : "transparent",
              fontWeight: selected === cfg.path ? 600 : 400,
              transition: "background 0.1s",
            }}
          >
            {cfg.name}
          </div>
        ))}
      </div>

      {/* Key-value editor */}
      <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
        {currentCfg && (
          <>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 16,
              }}
            >
              <div>
                <h3
                  style={{
                    fontSize: 14,
                    fontWeight: 600,
                    color: "var(--text-primary)",
                  }}
                >
                  {currentCfg.name}
                </h3>
                {currentCfg.description && (
                  <p
                    style={{
                      fontSize: 11,
                      color: "var(--text-muted)",
                      marginTop: 2,
                    }}
                  >
                    {currentCfg.description}
                  </p>
                )}
              </div>
              <button
                className="btn-primary"
                onClick={() => handleSave(currentCfg)}
                disabled={saving === currentCfg.path || edited.size === 0}
                style={{ fontSize: 12 }}
              >
                {saving === currentCfg.path ? "保存中..." : "保存"}
              </button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {currentCfg.keys.map((k) => {
                const vkey = `${currentCfg.path}::${k.key}`;
                const changed = edited.has(vkey);
                return (
                  <div
                    key={k.key}
                    style={{
                      padding: "10px 12px",
                      background: "var(--bg-secondary)",
                      border: "1px solid var(--border)",
                      borderRadius: "var(--radius-sm)",
                      display: "flex",
                      alignItems: "center",
                      gap: 12,
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          fontSize: 12,
                          fontWeight: 600,
                          fontFamily: "var(--mono)",
                          color: changed
                            ? "var(--yellow)"
                            : "var(--text-primary)",
                        }}
                      >
                        {k.key}
                        {changed && (
                          <span
                            style={{
                              fontSize: 10,
                              marginLeft: 6,
                              color: "var(--yellow)",
                            }}
                          >
                            *
                          </span>
                        )}
                      </div>
                      {k.description && (
                        <div
                          style={{
                            fontSize: 11,
                            color: "var(--text-muted)",
                            marginTop: 2,
                          }}
                        >
                          {k.description}
                        </div>
                      )}
                    </div>
                    {renderInput(k)}
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
