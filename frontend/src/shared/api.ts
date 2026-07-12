import axios from "axios";

import type { CurrentUser } from "./types";

/**
 * HTTP-клиент. Работает через тот же origin (Vite проксирует /api на backend),
 * поэтому сессионная кука и CSRF ходят автоматически.
 *
 * Текущий тенант передаётся заголовком X-Tenant-ID (см. TenantContextMiddleware).
 */
export const api = axios.create({
  baseURL: "/api",
  withCredentials: true,
  xsrfCookieName: "csrftoken",
  xsrfHeaderName: "X-CSRFToken",
});

export function setActiveTenant(tenantId: number | null) {
  if (tenantId == null) {
    delete api.defaults.headers.common["X-Tenant-ID"];
  } else {
    api.defaults.headers.common["X-Tenant-ID"] = String(tenantId);
  }
}

// --- Аутентификация --------------------------------------------------------
export async function ensureCsrf(): Promise<void> {
  await api.get("/auth/csrf/");
}

export async function fetchMe(): Promise<CurrentUser> {
  return (await api.get<CurrentUser>("/auth/me/")).data;
}

export async function login(username: string, password: string): Promise<CurrentUser> {
  await ensureCsrf(); // гарантируем cookie csrftoken для последующих POST
  return (await api.post<CurrentUser>("/auth/login/", { username, password })).data;
}

export async function logout(): Promise<void> {
  await api.post("/auth/logout/");
}
