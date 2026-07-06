// Thin fetch wrapper for the T2C Data Ingest API. Attaches the shared JWT (issued by
// t2c_data) from localStorage and normalizes errors.

const TOKEN_KEY = "t2c_ingest_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export interface Page<T> {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_more: boolean;
  items: T[];
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const resp = await fetch(`${BASE}${path}`, { ...init, headers });

  if (resp.status === 401) {
    setToken(null);
    throw new ApiError(401, "Sessão expirada. Faça login novamente.");
  }
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const data = await resp.json();
      detail = data.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(resp.status, typeof detail === "string" ? detail : "Erro na requisição");
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),

  // Login uses form-encoding (OAuth2 password flow), like t2c_data.
  async login(email: string, password: string): Promise<string> {
    const form = new URLSearchParams();
    form.set("username", email);
    form.set("password", password);
    const resp = await fetch(`${BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form.toString(),
    });
    if (!resp.ok) throw new ApiError(resp.status, "Credenciais inválidas");
    const data = (await resp.json()) as { access_token: string };
    return data.access_token;
  },
};
