from backend.app.core.permissions import Permission, has_permission, permission_values_for_role


def test_principal_can_manage_users_and_approve_adjustments():
    assert has_permission("principal", Permission.manage_users)
    assert has_permission("principal", Permission.approve_stock_adjustment)


def test_sales_can_invoice_but_cannot_dispatch():
    assert has_permission("ventas", Permission.register_invoice)
    assert not has_permission("ventas", Permission.confirm_dispatch)


def test_warehouse_can_dispatch_and_request_but_not_approve_adjustment():
    assert has_permission("bodega", Permission.confirm_dispatch)
    assert has_permission("bodega", Permission.request_stock_adjustment)
    assert not has_permission("bodega", Permission.approve_stock_adjustment)


def test_consultation_role_is_read_only():
    assert has_permission("consulta", Permission.view_inventory)
    assert not has_permission("consulta", Permission.register_invoice)


def test_permission_values_are_ready_for_the_frontend():
    assert permission_values_for_role("bodega") == [
        "confirm_dispatch",
        "request_stock_adjustment",
        "view_inventory",
    ]
