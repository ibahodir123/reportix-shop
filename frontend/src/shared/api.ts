import axios from "axios";

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
