from enum import Enum

class Permission(str, Enum):
    view_inventory = "view_inventory"
    register_invoice = "register_invoice"
    manage_reservations = "manage_reservations"
    confirm_dispatch = "confirm_dispatch"
    request_stock_adjustment = "request_stock_adjustment"
    approve_stock_adjustment = "approve_stock_adjustment"
    manage_users = "manage_users"


ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "principal": frozenset(Permission),
    "administracion": frozenset(
        {
            Permission.view_inventory,
            Permission.register_invoice,
            Permission.manage_reservations,
        }
    ),
    "ventas": frozenset(
        {
            Permission.view_inventory,
            Permission.register_invoice,
            Permission.manage_reservations,
        }
    ),
    "bodega": frozenset(
        {
            Permission.view_inventory,
            Permission.confirm_dispatch,
            Permission.request_stock_adjustment,
        }
    ),
    "consulta": frozenset({Permission.view_inventory}),
}


def has_permission(role: str, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())


def permission_values_for_role(role: str) -> list[str]:
    return sorted(permission.value for permission in ROLE_PERMISSIONS.get(role, frozenset()))
