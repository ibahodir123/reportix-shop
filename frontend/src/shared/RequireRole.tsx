import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "./auth";
import { canAccess } from "./roles";
import type { Role } from "./types";

/**
 * Дополнительная frontend-защита маршрута по роли (основная — на backend).
 * Пользователя без нужной роли (например, кассира на /products) уводим на POS.
 */
export function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { user, isLoading } = useAuth();
  if (isLoading) return null;
  if (!canAccess(user?.role, roles)) {
    return <Navigate to="/pos" replace />;
  }
  return <>{children}</>;
}
