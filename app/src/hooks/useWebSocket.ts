import { useEffect, useRef, useCallback } from "react";
import { useSettings } from "../store/settings";

export function useWebSocket(
  path: string,
  onMessage: (data: string) => void,
  enabled = true
) {
  const wsRef = useRef<WebSocket | null>(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const apiUrl = useSettings((s) => s.apiUrl);
  const token = useSettings((s) => s.token);

  const connect = useCallback(() => {
    if (!enabled) return;

    const wsUrl = apiUrl.replace(/^http/, "ws") + path + `?token=${token || ""}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (e) => onMessageRef.current(e.data as string);
    ws.onclose = () => {
      wsRef.current = null;
    };

    return ws;
  }, [apiUrl, path, enabled, token]);

  useEffect(() => {
    const ws = connect();
    return () => {
      ws?.close();
      wsRef.current = null;
    };
  }, [connect]);

  return {
    send: useCallback((data: string) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(data);
      }
    }, []),
    reconnect: connect,
  };
}
