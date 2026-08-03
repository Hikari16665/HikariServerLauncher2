import { useCallback, useEffect, useRef, useState } from "react";
import { useSettings } from "../store/settings";

export function useWebSocket(
  path: string,
  onMessage: (data: string) => void,
  enabled = true,
  skipHistoryOnReconnect = false
) {
  const wsRef = useRef<WebSocket | null>(null);
  const onMessageRef = useRef(onMessage);
  const [reconnectNonce, setReconnectNonce] = useState(0);

  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  const apiUrl = useSettings((s) => s.apiUrl);
  const token = useSettings((s) => s.token);

  useEffect(() => {
    if (!enabled) return;
    let disposed = false;
    let retryCount = 0;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = (isReconnect: boolean) => {
      if (disposed) return;
      let wsUrl = apiUrl.replace(/^http/, "ws") + path;
      if (skipHistoryOnReconnect && isReconnect) wsUrl += "?skip_history=1";
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onopen = () => {
        ws.send(JSON.stringify({ type: "auth", token: token || "" }));
        retryCount = 0;
      };
      ws.onmessage = (event) => onMessageRef.current(event.data as string);
      ws.onclose = () => {
        if (wsRef.current === ws) wsRef.current = null;
        if (disposed) return;
        const delay =
          Math.min(30000, 1000 * 2 ** Math.min(retryCount++, 5)) + Math.random() * 500;
        retryTimer = setTimeout(() => connect(true), delay);
      };
    };

    connect(reconnectNonce > 0);
    return () => {
      disposed = true;
      if (retryTimer) clearTimeout(retryTimer);
      const ws = wsRef.current;
      if (ws) ws.onclose = null;
      ws?.close();
      wsRef.current = null;
    };
  }, [apiUrl, path, enabled, token, skipHistoryOnReconnect, reconnectNonce]);

  return {
    send: useCallback((data: string) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(data);
      }
    }, []),
    reconnect: useCallback(() => {
      setReconnectNonce((value) => value + 1);
    }, []),
  };
}
