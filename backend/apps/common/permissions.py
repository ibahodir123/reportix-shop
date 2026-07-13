"""
RBAC-разрешения по роли текущего членства (request.membership.role).

Роли: owner (полный доступ), manager (товары/склад/приёмка/касса, без
управления пользователями и настройками), cashier (только касса + чтение
вариантов/остатков для POS).

Источник роли — request.membership (проставляет TenantContextMiddleware).
Нет членства → доступ запрещён (403).
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

# Значения совпадают с apps.tenants.models.Membership.ROLE_*.
OWNER = "owner"
MANAGER = "manager"
CASHIER = "cashier"


def current_role(request):
    membership = getattr(request, "membership", None)
    return membership.role if membership is not None else None


class RolePermission(BasePermission):
    """Базовый класс: read_roles для safe-методов, write_roles для остальных."""

    message = "Недостаточно прав для этого действия."
    read_roles = frozenset()
    write_roles = frozenset()

    def has_permission(self, request, view):
        role = current_role(request)
        if role is None:
            return False  # нет членства текущего тенанта
        allowed = self.read_roles if request.method in SAFE_METHODS else self.write_roles
        return role in allowed


def _perm(read, write=None, name="RolePerm"):
    write = read if write is None else write
    return type(
        name,
        (RolePermission,),
        {"read_roles": frozenset(read), "write_roles": frozenset(write)},
    )


# Товары/справочники каталога, quick-product, голосовой ввод — owner+manager.
ManageCatalog = _perm({OWNER, MANAGER}, name="ManageCatalog")

# Варианты: чтение (поиск в POS) — все роли; изменение — owner+manager.
VariantsAccess = _perm({OWNER, MANAGER, CASHIER}, {OWNER, MANAGER}, name="VariantsAccess")

# Склад/движения/приёмка — owner+manager.
ManageInventory = _perm({OWNER, MANAGER}, name="ManageInventory")

# Остатки (read-only) — все роли (POS может читать необходимые остатки).
StockRead = _perm({OWNER, MANAGER, CASHIER}, name="StockRead")

# Кассы (справочник): чтение — все (POS выбирает кассу); изменение — owner+manager.
RegistersAccess = _perm({OWNER, MANAGER, CASHIER}, {OWNER, MANAGER}, name="RegistersAccess")

# Касса (смены, чеки) — все роли.
PosAccess = _perm({OWNER, MANAGER, CASHIER}, {OWNER, MANAGER, CASHIER}, name="PosAccess")
