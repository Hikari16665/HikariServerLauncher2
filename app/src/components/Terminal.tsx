import { useEffect, useRef, useState } from "react";
import { Terminal as XTerm } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import "@xterm/xterm/css/xterm.css";
import { useWebSocket } from "../hooks/useWebSocket";

interface Props {
  serverUuid: string;
  running?: boolean;
}

export default function Terminal({ serverUuid }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<XTerm | null>(null);
  const fitRef = useRef<FitAddon | null>(null);
  const bufRef = useRef("");
  const [encoding, setEncoding] = useState<"utf-8" | "gbk">("utf-8");

  const { send } = useWebSocket(
    `/api/servers/${serverUuid}/terminal`,
    (raw: string) => {
      try {
        const msg = JSON.parse(raw);
        if (msg.type === "log") {
          termRef.current?.write(msg.line + "\r\n");
        } else if (msg.type === "status") {
          termRef.current?.write(`\x1b[90m${msg.message}\x1b[0m\r\n`);
        } else if (msg.type === "error") {
          termRef.current?.write(`\x1b[91m${msg.message}\x1b[0m\r\n`);
        }
      } catch {
        termRef.current?.write(raw);
      }
    },
    true,
    true
  );

  useEffect(() => {
    const term = new XTerm({
      cursorBlink: true,
      cursorStyle: "bar",
      fontSize: 13,
      fontFamily: "var(--mono)",
      theme: {
        background: "#0d1117",
        foreground: "#e6edf3",
        cursor: "#58a6ff",
        selectionBackground: "#30363d",
        black: "#21262d",
        red: "#f85149",
        green: "#3fb950",
        yellow: "#d29922",
        blue: "#58a6ff",
        magenta: "#a371f7",
        cyan: "#39c5cf",
        white: "#e6edf3",
        brightBlack: "#8b949e",
        brightRed: "#ff7b72",
        brightGreen: "#56d364",
        brightYellow: "#e3b341",
        brightBlue: "#79c0ff",
        brightMagenta: "#bc8cff",
        brightCyan: "#56d4dd",
        brightWhite: "#ffffff",
      },
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.loadAddon(new WebLinksAddon());

    term.open(containerRef.current!);
    fitAddon.fit();

    term.onData((data) => {
      if (data === "\r") {
        // Enter — send buffered command
        if (bufRef.current.trim()) {
          send(JSON.stringify({ type: "command", command: bufRef.current }));
        }
        bufRef.current = "";
        term.write("\r\n");
      } else if (data === "\x7f" || data === "\b") {
        // Backspace
        if (bufRef.current.length > 0) {
          bufRef.current = bufRef.current.slice(0, -1);
          term.write("\b \b");
        }
      } else if (data === "") {
        // Ctrl+C — clear buffer
        bufRef.current = "";
        term.write("^C\r\n");
      } else if (data.length === 1 && data.charCodeAt(0) >= 32) {
        // Printable characters
        bufRef.current += data;
        term.write(data);
      }
    });

    termRef.current = term;
    fitRef.current = fitAddon;

    const handleResize = () => fitAddon.fit();
    const observer = new ResizeObserver(handleResize);
    observer.observe(containerRef.current!);
    window.addEventListener("resize", handleResize);

    return () => {
      term.dispose();
      observer.disconnect();
      window.removeEventListener("resize", handleResize);
    };
  }, [serverUuid]);

  function toggleEncoding() {
    const next = encoding === "utf-8" ? "gbk" : "utf-8";
    setEncoding(next);
    send(JSON.stringify({ type: "set_encoding", encoding: next }));
    termRef.current?.write(`\x1b[90m[编码切换: ${next.toUpperCase()}]\x1b[0m\r\n`);
  }

  return (
    <div style={{ position: "relative", height: "100%" }}>
      <div
        ref={containerRef}
        style={{
          height: "100%",
          padding: "8px 12px 12px 12px",
          background: "#0d1117",
          boxSizing: "border-box",
        }}
      />
      <button
        onClick={toggleEncoding}
        title={`当前编码: ${encoding.toUpperCase()}，点击切换`}
        style={{
          position: "absolute",
          top: 8,
          right: 20,
          padding: "3px 8px",
          fontSize: 11,
          fontFamily: "var(--mono)",
          fontWeight: 600,
          background: "rgba(48,54,61,0.85)",
          color: "var(--text-muted)",
          border: "1px solid rgba(139,148,158,0.3)",
          borderRadius: 4,
          cursor: "pointer",
          zIndex: 10,
          transition: "color 0.15s, border-color 0.15s",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.color = "#e6edf3";
          e.currentTarget.style.borderColor = "rgba(139,148,158,0.6)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.color = "var(--text-muted)";
          e.currentTarget.style.borderColor = "rgba(139,148,158,0.3)";
        }}
      >
        {encoding.toUpperCase()}
      </button>
    </div>
  );
}
