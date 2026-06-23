from __future__ import annotations

from io import BytesIO

from order_parsers import detect_chain_and_parse


class PurchaseOrderFileError(Exception):
    pass


def parse_purchase_order_pdf(filename: str, content: bytes) -> tuple[str | None, list[dict[str, object]]]:
    if not filename.lower().endswith(".pdf"):
        raise PurchaseOrderFileError("Solo se permiten archivos PDF para detectar OCs.")
    if not content:
        raise PurchaseOrderFileError("El archivo PDF esta vacio.")

    try:
        chain_name, parsed_rows = detect_chain_and_parse(BytesIO(content))
    except Exception as exc:  # pragma: no cover - parser externo legado
        raise PurchaseOrderFileError("No se pudo leer el PDF de la OC.") from exc

    if not parsed_rows:
        raise PurchaseOrderFileError(
            "No se detectaron productos en la OC. Revisa el archivo o registra la OC manualmente."
        )

    return (
        None if chain_name == "DESCONOCIDA" else str(chain_name),
        [
            {
                "sku": str(row["SKU"]).upper().strip(),
                "requested_quantity": int(row["Cantidad"]),
                "original_description": str(row.get("Desc_Original") or "").strip() or None,
            }
            for row in parsed_rows
            if row.get("SKU") and int(row.get("Cantidad") or 0) > 0
        ],
    )
