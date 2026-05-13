import { useEffect, useRef, useCallback } from "react";
import { useSettings } from "../store/settings";

export function useWebSocket(
  path: string,
  onMessage: (data: string) => void,
  enabled = true,
  skipHistoryOnReconnect = false
) {
  const wsRef = useRef<WebSocket | null>(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const apiUrl = useSettings((s) => s.apiUrl);
  const token = useSettings((s) => s.token);

  const connect = useCallback((isReconnect = false) => {
    if (!enabled) return;

    let wsUrl = apiUrl.replace(/^http/, "ws") + path + `?token=${token || ""}`;
    if (skipHistoryOnReconnect && isReconnect) {
      wsUrl += "&skip_history=1";
    }
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (e) => onMessageRef.current(e.data as string);
    ws.onclose = () => {
      wsRef.current = null;
    };

    return ws;
  }, [apiUrl, path, enabled, token, skipHistoryOnReconnect]);

  useEffect(() => {
    const ws = connect(false);
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
    reconnect: useCallback(() => {
      connect(true);
    }, [connect]),
  };
}
