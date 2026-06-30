from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


LINE_PATTERN = re.compile(
    r"^\s*(?:[-*•]\s*)?(\d+(?:[.,]\d+)?)\s*"
    r"(?:(?:UNIDADES?|UNDS?|UDS?)\.?\s*)?(?:[xX]\s+)?(.+?)\s*(?:-\s*)?$",
    re.IGNORECASE,
)
SEPARATOR_PATTERN = re.compile(r"^\s*[-_=*]{3,}\s*$")
BLOCK_HEADER_PATTERN = re.compile(
    r"^\s*(FACTURA|FAC(?:T)?\.?|BLOQUE)\s*(?:(?:N(?:RO|O)?\.?|N[°º]|#)\s*)?"
    r"[:\-]?\s*(\S.*?)\s*$",
    re.IGNORECASE,
)
PURCHASE_ORDER_HEADER_PATTERN = re.compile(
    r"^\s*(?:OC|ORDEN\s+DE\s+COMPRA)\s*(?:(?:N(?:RO|O)?\.?|N[°º]|#)\s*)?"
    r"[:\-]?\s*(\S.*?)\s*$",
    re.IGNORECASE,
)
IGNORED_HEADER_PATTERN = re.compile(
    r"^\s*(?:CLIENTE|PRODUCTO|DESCRIPCI[OÓ]N|CANTIDAD)(?:\s|:|#|-|$).*$",
    re.IGNORECASE,
)


def normalize_product_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.upper()
    normalized = re.sub(r"[^A-Z0-9\s]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


@dataclass
class ParsedBulkLine:
    quantity: int
    raw_description: str
    normalized_description: str
    invoice_number: str | None = None
    purchase_order_number: str | None = None


class BulkInvoiceParseError(Exception):
    pass


def parse_bulk_invoice_text(raw_text: str) -> list[list[ParsedBulkLine]]:
    text = (raw_text or "").strip()
    if not text:
        raise BulkInvoiceParseError("Pega el contenido de las facturas antes de revisar.")

    groups: list[list[ParsedBulkLine]] = []
    current_group: list[ParsedBulkLine] = []
    current_invoice_number: str | None = None
    current_purchase_order_number: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        block_header = BLOCK_HEADER_PATTERN.match(line)
        if block_header:
            if current_group:
                groups.append(current_group)
                current_group = []
            header_type, header_value = block_header.groups()
            current_invoice_number = (
                header_value.strip()
                if header_type.upper().startswith("FAC") and any(char.isdigit() for char in header_value)
                else None
            )
            current_purchase_order_number = None
            continue
        purchase_order_header = PURCHASE_ORDER_HEADER_PATTERN.match(line)
        if purchase_order_header:
            current_purchase_order_number = purchase_order_header.group(1).strip()
            continue
        if SEPARATOR_PATTERN.match(line):
            if current_group:
                groups.append(current_group)
                current_group = []
            current_invoice_number = None
            current_purchase_order_number = None
            continue
        if IGNORED_HEADER_PATTERN.match(line):
            continue

        match = LINE_PATTERN.match(line)
        if not match:
            raise BulkInvoiceParseError(f"No pude leer esta linea: {raw_line.strip()}")

        quantity_text, description = match.groups()
        quantity_number = float(quantity_text.replace(",", "."))
        if quantity_number <= 0:
            raise BulkInvoiceParseError(
                f"La cantidad debe ser mayor que cero. Revisa la linea: {raw_line.strip()}"
            )
        if int(quantity_number) != quantity_number:
            raise BulkInvoiceParseError(
                f"La cantidad debe ser entera en unidades. Revisa la linea: {raw_line.strip()}"
            )
        current_group.append(
            ParsedBulkLine(
                quantity=int(quantity_number),
                raw_description=description.strip(" -"),
                normalized_description=normalize_product_text(description),
                invoice_number=current_invoice_number,
                purchase_order_number=current_purchase_order_number,
            )
        )

    if current_group:
        groups.append(current_group)

    if not groups:
        raise BulkInvoiceParseError("No se detectaron facturas en el texto pegado.")

    return groups
