from backend.app.services.availability import calculate_available_to_invoice


def test_available_to_invoice_uses_confirmed_formula():
    assert calculate_available_to_invoice(
        physical_confirmed=100,
        reserved=10,
        invoiced_pending_dispatch=25,
        blocked_incident=5,
    ) == 60


def test_available_to_invoice_never_goes_negative():
    assert calculate_available_to_invoice(
        physical_confirmed=10,
        reserved=20,
        invoiced_pending_dispatch=5,
        blocked_incident=5,
    ) == 0
