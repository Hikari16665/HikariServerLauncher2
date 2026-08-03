import { useEffect, useRef, useCallback } from "react";
import { useSettings } from "../store/settings";

export function useWebSocket(
  path: string,
  onMessage: (data: string) => void,
  enabled = true,
  skipHistoryOnReconnect = false
) {
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const disposedRef = useRef(false);
  const retryCountRef = useRef(0);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const apiUrl = useSettings((s) => s.apiUrl);
  const token = useSettings((s) => s.token);

  const connect = useCallback((isReconnect = false) => {
    if (!enabled) return;

    if (retryRef.current) {
      clearTimeout(retryRef.current);
      retryRef.current = null;
    }
    const previous = wsRef.current;
    if (previous) {
      previous.onclose = null;
      previous.onmessage = null;
      previous.close();
    }

    let wsUrl = apiUrl.replace(/^http/, "ws") + path + `?token=${token || ""}`;
    if (skipHistoryOnReconnect && isReconnect) {
      wsUrl += "&skip_history=1";
    }
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => { retryCountRef.current = 0; };
    ws.onmessage = (e) => onMessageRef.current(e.data as string);
    ws.onclose = () => {
      if (wsRef.current !== ws) return;
      wsRef.current = null;
      if (enabled && !disposedRef.current) {
        const attempt = retryCountRef.current++;
        const delay = Math.min(30000, 1000 * 2 ** Math.min(attempt, 5)) + Math.random() * 500;
        retryRef.current = setTimeout(() => connect(true), delay);
      }
    };

    return ws;
  }, [apiUrl, path, enabled, token, skipHistoryOnReconnect]);

  useEffect(() => {
    disposedRef.current = false;
    const ws = connect(false);
    return () => {
      disposedRef.current = true;
      if (ws) {
        ws.onclose = null;
        ws.onmessage = null;
      }
      ws?.close();
      if (retryRef.current) clearTimeout(retryRef.current);
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
