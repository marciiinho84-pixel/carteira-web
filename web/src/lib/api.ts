const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "https://minhacarteira.duckdns.org/api/v1";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("carteira_token");
}

export function setToken(token: string) {
  localStorage.setItem("carteira_token", token);
}

export function clearToken() {
  localStorage.removeItem("carteira_token");
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? "Erro na API");
  }
  return res.json() as Promise<T>;
}

export const auth = {
  requestLink: (email: string) =>
    apiFetch<{ message: string }>("/auth/request-link", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  verify: (token: string) =>
    apiFetch<{ access_token: string; token_type: string }>(
      `/auth/verify?token=${encodeURIComponent(token)}`
    ),

  me: () => apiFetch<{ email: string }>("/auth/me"),
};

export const apiStatus = () =>
  apiFetch<{ status: string; version: string }>("/health");
