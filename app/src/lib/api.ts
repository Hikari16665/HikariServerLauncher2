import { invoke } from "@tauri-apps/api/core";
import { useSettings } from "../store/settings";
import { useToastStore } from "../store/toast";

interface ProxyResponse {
  status: number;
  body: string;
  error: string | null;
}

let refreshPromise: Promise<boolean> | null = null;

async function tryRefreshToken(): Promise<boolean> {
  const { adminKey, setToken, clearAuth } = useSettings.getState();
  if (!adminKey) return false;
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    try {
      const { apiUrl } = useSettings.getState();
      const resp = await invoke<ProxyResponse>("proxy_fetch", {
        req: {
          url: `${apiUrl}/api/auth`,
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ auth_key: adminKey }),
        },
      });
      if (resp.error) return false;
      const data = JSON.parse(resp.body);
      if (data.success && data.token) {
        setToken(data.token);
        return true;
      }
      return false;
    } catch {
      clearAuth();
      return false;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

function dumpError(e: unknown): string {
  if (e === null || e === undefined) return String(e);
  if (typeof e === "string") return e;
  if (typeof e === "object") {
    try { return JSON.stringify(e, null, 2); } catch {}
  }
  return String(e);
}

async function invokeFetch(method: string, url: string, body: string | null, headers: Record<string, string>): Promise<ProxyResponse> {
  const detail = [`请求: ${method} ${url}`, `Body: ${body || "(空)"}`, `Headers: ${JSON.stringify(headers)}`].join("\n");

  try {
    const resp = await invoke<ProxyResponse>("proxy_fetch", {
      req: { url, method, headers, body },
    });
    return resp;
  } catch (e: unknown) {
    throw new FetchError("无法连接到服务器", `${detail}\n\n系统错误:\n${dumpError(e)}`);
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  retry = true
): Promise<T> {
  const { apiUrl, token } = useSettings.getState();

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const url = `${apiUrl}${path}`;
  const method = options.method || "GET";
  const body = typeof options.body === "string" ? options.body : null;

  if (method !== "GET" && body) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
  }

  const resp = await invokeFetch(method, url, body, headers);

  if (resp.error) {
    const detail = `${method} ${url}\n${resp.error}`;
    throw new FetchError("网络请求失败", detail);
  }

  if (resp.status === 401 && retry) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      return apiRequest<T>(path, options, false);
    }
    useSettings.getState().clearAuth();
    useToastStore.getState().addToast("认证已过期，请重新登录", "error", `${method} ${url}\n状态: 401`);
    throw new ApiError(401, "Authentication failed");
  }

  if (resp.status < 200 || resp.status >= 300) {
    let errorMsg = `HTTP ${resp.status}`;
    try { const b = JSON.parse(resp.body); if (b.error) errorMsg = b.error; } catch {}
    throw new ApiError(resp.status, errorMsg, `${method} ${url}\n状态: ${resp.status}\n响应: ${resp.body.slice(0, 500)}`);
  }

  return JSON.parse(resp.body) as T;
}

export class ApiError extends Error {
  status: number;
  detail?: string;
  constructor(status: number, msg: string, detail?: string) {
    super(msg);
    this.status = status;
    this.detail = detail;
  }
}

export class FetchError extends Error {
  detail: string;
  constructor(msg: string, detail: string) {
    super(msg);
    this.detail = detail;
  }
}

export const api = {
  get: <T>(path: string) => apiRequest<T>(path),
  post: <T>(path: string, body?: unknown) =>
    apiRequest<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    }),
  put: <T>(path: string, body?: unknown) =>
    apiRequest<T>(path, {
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined,
    }),
  delete: <T>(path: string) =>
    apiRequest<T>(path, { method: "DELETE" }),
};
