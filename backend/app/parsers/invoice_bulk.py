from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


LINE_PATTERN = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s+(.+?)\s*(?:-\s*)?$")
SEPARATOR_PATTERN = re.compile(r"^\s*-{3,}\s*$")


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


class BulkInvoiceParseError(Exception):
    pass


def parse_bulk_invoice_text(raw_text: str) -> list[list[ParsedBulkLine]]:
    text = (raw_text or "").strip()
    if not text:
        raise BulkInvoiceParseError("Pega el contenido de las facturas antes de revisar.")

    groups: list[list[ParsedBulkLine]] = []
    current_group: list[ParsedBulkLine] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if SEPARATOR_PATTERN.match(line):
            if current_group:
                groups.append(current_group)
                current_group = []
            continue

        match = LINE_PATTERN.match(line)
        if not match:
            raise BulkInvoiceParseError(f"No pude leer esta linea: {raw_line.strip()}")

        quantity_text, description = match.groups()
        quantity_number = float(quantity_text.replace(",", "."))
        if int(quantity_number) != quantity_number:
            raise BulkInvoiceParseError(
                f"La cantidad debe ser entera en unidades. Revisa la linea: {raw_line.strip()}"
            )
        current_group.append(
            ParsedBulkLine(
                quantity=int(quantity_number),
                raw_description=description.strip(" -"),
                normalized_description=normalize_product_text(description),
            )
        )

    if current_group:
        groups.append(current_group)

    if not groups:
        raise BulkInvoiceParseError("No se detectaron facturas en el texto pegado.")

    return groups
