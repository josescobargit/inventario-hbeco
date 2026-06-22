def calculate_available_to_invoice(
    physical_confirmed: int,
    reserved: int,
    invoiced_pending_dispatch: int,
    blocked_incident: int,
) -> int:
    """Formula confirmada por negocio.

    Disponible para facturar =
    stock fisico confirmado - reservado - facturado no despachado - bloqueado por incidencia.
    """
    return max(
        0,
        int(physical_confirmed)
        - int(reserved)
        - int(invoiced_pending_dispatch)
        - int(blocked_incident),
    )
