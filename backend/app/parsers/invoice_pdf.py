from __future__ import annotations

import re
from datetime import datetime
from io import BytesIO

import pdfplumber


class InvoiceFileError(Exception):
    pass


def parse_contifico_invoice_pdf(filename: str, content: bytes) -> dict[str, object]:
    if not filename.lower().endswith(".pdf"):
        raise InvoiceFileError("Solo se permiten archivos PDF de factura.")
    if not content:
        raise InvoiceFileError("El archivo de factura esta vacio.")

    try:
        with pdfplumber.open(BytesIO(content)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as exc:
        raise InvoiceFileError("No se pudo leer el PDF de la factura.") from exc

    invoice_match = re.search(r"FACTURA\s+NO\.\s*([\d-]+)", text, re.IGNORECASE)
    authorization_match = re.search(r"N[ÚU]MERO DE AUTORIZACI[ÓO]N:\s*(\d{30,})", text, re.IGNORECASE)
    issued_match = re.search(r"FECHA EMISI[ÓO]N:\s*(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
    customer_match = re.search(r"RAZ[ÓO]N SOCIAL:\s*(.+?)\s+RUC/CI:", text, re.IGNORECASE)
    order_match = re.search(r"ORDEN DE COMPRA\s+NO\.\s*(\d+)", text, re.IGNORECASE)
    total_match = re.search(r"VALOR TOTAL:\s*\$?([\d,.]+)", text, re.IGNORECASE)

    lines = []
    line_pattern = re.compile(
        r"^([A-Z]{2,4}\d{3})\s+(\d+(?:[.,]\d+)?)\s+(.+?)\s+([\d.]+)\s+\$?[\d,.]+\s+\$?[\d,.]+$"
    )
    pending: str | None = None
    for raw_line in text.splitlines():
        stripped = " ".join(raw_line.split())
        if re.match(r"^[A-Z]{2,4}\d{3}\s+\d", stripped):
            pending = stripped
        elif pending and stripped and not re.match(r"^(INFORMACI[ÓO]N|SUBTOTAL|DESCRIPCI[ÓO]N)", stripped, re.IGNORECASE):
            pending = f"{pending} {stripped}"
        else:
            pending = None

        if not pending:
            continue
        match = line_pattern.match(pending)
        if not match:
            continue
        quantity = float(match.group(2).replace(",", "."))
        if not quantity.is_integer():
            raise InvoiceFileError(f"La factura contiene una cantidad fraccionaria para {match.group(1)}.")
        lines.append(
            {
                "sku": match.group(1).upper(),
                "quantity": int(quantity),
                "description": match.group(3).strip(),
            }
        )
        pending = None

    if not invoice_match or not lines:
        raise InvoiceFileError("No pude detectar el numero o los productos de la factura.")

    issued_at = None
    if issued_match:
        issued_at = datetime.strptime(issued_match.group(1), "%d/%m/%Y")
    total_amount = None
    if total_match:
        total_amount = float(total_match.group(1).replace(",", ""))

    return {
        "invoice_number": invoice_match.group(1),
        "authorization_number": authorization_match.group(1) if authorization_match else None,
        "issued_at": issued_at,
        "customer_name": customer_match.group(1).strip() if customer_match else None,
        "purchase_order_number": order_match.group(1) if order_match else None,
        "total_amount": total_amount,
        "source_filename": filename,
        "lines": lines,
    }
