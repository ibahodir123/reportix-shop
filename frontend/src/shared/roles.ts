import type { Role } from "./types";

// Роли, управляющие каталогом/складом (owner + manager).
export const MANAGE_ROLES: Role[] = ["owner", "manager"];
export const ALL_ROLES: Role[] = ["owner", "manager", "cashier"];

export function canAccess(role: Role | null | undefined, allowed: Role[]): boolean {
  return !!role && allowed.includes(role);
}

// Навигация с ролями, которым доступен раздел.
export interface NavEntry {
  key: string;
  label: string;
  roles: Role[];
}

export const NAV: NavEntry[] = [
  { key: "/dashboard", label: "Сводка", roles: ALL_ROLES },
  { key: "/pos", label: "Касса", roles: ALL_ROLES },
  { key: "/returns", label: "Возвраты", roles: ALL_ROLES },
  { key: "/receiving", label: "Приёмка", roles: MANAGE_ROLES },
  { key: "/products", label: "Товары", roles: MANAGE_ROLES },
  { key: "/voice", label: "Голосовой ввод", roles: MANAGE_ROLES },
  { key: "/assistant", label: "Помощник", roles: MANAGE_ROLES },
];

export function visibleNav(role: Role | null | undefined): NavEntry[] {
  return NAV.filter((entry) => canAccess(role, entry.roles));
}
