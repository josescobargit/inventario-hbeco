from __future__ import annotations

import re
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

import pdfplumber


class PurchaseOrderFileError(Exception):
    pass


def _iso_date(value: str | None, formats: tuple[str, ...]) -> date | None:
    if not value:
        return None
    for date_format in formats:
        try:
            return datetime.strptime(value.strip(), date_format).date()
        except ValueError:
            continue
    return None


def _line(
    *,
    description: str,
    requested_quantity: int,
    units_per_case: int,
    quantity_cases: int | None = None,
    sku_hint: str | None = None,
    barcode: str | None = None,
    external_product_code: str | None = None,
) -> dict[str, object]:
    return {
        "sku_hint": sku_hint,
        "barcode": barcode,
        "external_product_code": external_product_code,
        "requested_quantity": requested_quantity,
        "quantity_cases": quantity_cases,
        "units_per_case": units_per_case,
        "original_description": " ".join(description.split()),
    }


def _first_order_number(text: str, patterns: tuple[str, ...]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _filename_order_hint(filename: str) -> str:
    match = re.search(r"(?:^|\b)(?:OC|ORDEN)[\s_-]*(\d{5,})\b", Path(filename).stem, re.IGNORECASE)
    return match.group(1) if match else ""


def _parse_tia(pdf: pdfplumber.PDF, text: str) -> list[dict[str, object]]:
    homologation: dict[str, str] = {}
    product_rows: list[list[object]] = []
    for page in pdf.pages:
        for table in page.extract_tables():
            for row in table:
                if not row:
                    continue
                if len(row) > 8 and str(row[0] or "").strip().isdigit():
                    external_code = str(row[0] or "").strip()
                    sku = str(row[8] or "").strip().upper()
                    if len(external_code) == 9 and re.fullmatch(r"[A-Z]{2,3}\d{3}", sku):
                        homologation[external_code] = sku
                if len(row) > 13 and str(row[0] or "").strip().isdigit():
                    quantity = str(row[0] or "").strip()
                    cases = str(row[2] or "").strip()
                    description = str(row[6] or "").strip()
                    external_code = str(row[11] or "").strip()
                    if quantity and cases and description and len(external_code) == 9:
                        product_rows.append(row)

    lines = []
    for row in product_rows:
        quantity = int(str(row[0]).strip())
        cases = int(str(row[2]).strip())
        external_code = str(row[11]).strip()
        lines.append(
            _line(
                description=str(row[6]),
                requested_quantity=quantity,
                quantity_cases=cases,
                units_per_case=max(1, round(quantity / cases)),
                sku_hint=homologation.get(external_code),
                external_product_code=external_code,
            )
        )

    order_match = re.search(r"ORDEN DE COMPRA\s*N?[º°]?\s*(\d+)", text, re.IGNORECASE)
    order_date = re.search(r"FECHA DE LA ORDEN\s*:\s*(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
    delivery = re.search(
        r"DESDE EL:\s*HASTA EL:\s*(\d{4}-\d{2}-\d{2})\s+(\d{4}-\d{2}-\d{2})",
        text,
        re.IGNORECASE,
    )
    destination = re.search(
        r"CENTRO DE DISTRIBUCION NACIONAL:\s*([^\n]+)", text, re.IGNORECASE
    )
    return [
        {
            "chain_name": "TIA",
            "order_number": order_match.group(1) if order_match else "",
            "order_number_source": "document" if order_match else "missing",
            "order_date": _iso_date(order_date.group(1) if order_date else None, ("%Y-%m-%d",)),
            "delivery_start_date": _iso_date(delivery.group(1) if delivery else None, ("%Y-%m-%d",)),
            "delivery_due_date": _iso_date(delivery.group(2) if delivery else None, ("%Y-%m-%d",)),
            "destination": destination.group(1).strip() if destination else None,
            "external_reference": None,
            "lines": lines,
        }
    ]


def _parse_gerardo_ortiz(text: str) -> list[dict[str, object]]:
    rows = []
    pending_barcode: str | None = None
    pattern = re.compile(r"^\d+\s+(.+?)\s+X900[^\s]*-UN\s+(\d+)\s+", re.IGNORECASE)
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        barcode_match = re.match(r"(\d{13})(?:\s|$)", stripped)
        if barcode_match:
            pending_barcode = barcode_match.group(1)
            continue
        match = pattern.search(stripped)
        if not match:
            continue
        quantity = int(match.group(2))
        rows.append(
            _line(
                description=match.group(1),
                requested_quantity=quantity,
                units_per_case=1,
                barcode=pending_barcode,
            )
        )
        pending_barcode = None

    purchase_number = re.search(r"PED\.\s*COMPRA:\s*(\d+)", text, re.IGNORECASE)
    external = re.search(r"GERARDO ORTIZ E HIJOS CIA\s+(SD\d+)", text, re.IGNORECASE)
    sent_at = re.search(r"FECHA[^\n]{0,12}ENV[ÍI]O:\s*(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
    due_at = re.search(r"FECHA\.\s*LIMIT\.\s*ENTREGA:\s*(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
    destination = re.search(r"\d+\s+-\s+(TIENDA[^\n]+)", text, re.IGNORECASE)
    return [
        {
            "chain_name": "GERARDO ORTIZ",
            "order_number": purchase_number.group(1) if purchase_number else "",
            "order_number_source": "document" if purchase_number else "missing",
            "order_date": _iso_date(sent_at.group(1) if sent_at else None, ("%Y-%m-%d",)),
            "delivery_start_date": None,
            "delivery_due_date": _iso_date(due_at.group(1) if due_at else None, ("%Y-%m-%d",)),
            "destination": destination.group(1).strip() if destination else None,
            "external_reference": external.group(1).upper() if external else None,
            "lines": rows,
        }
    ]


def _parse_favorita(text: str, filename: str) -> list[dict[str, object]]:
    rows = []
    pattern = re.compile(
        r"^\d+\s*(.+?)\s+(?:[A-Z0-9]+\s+)?(\d{13})\s+(6|12|288)\s+[\d.]+\s+(\d+)\s*$",
        re.IGNORECASE,
    )
    for raw_line in text.splitlines():
        match = pattern.search(raw_line.strip())
        if not match:
            continue
        units_per_case = int(match.group(3))
        cases = int(match.group(4))
        rows.append(
            _line(
                description=match.group(1),
                requested_quantity=cases * units_per_case,
                quantity_cases=cases,
                units_per_case=units_per_case,
                barcode=match.group(2),
            )
        )

    order_number = _first_order_number(
        text,
        (
            r"N[ÚU]MERO\s+(?:DE\s+)?ORDEN\s*[:#-]?\s*(\d{5,})",
            r"ORDEN\s+(?:DE\s+)?COMPRA\s+(?:N(?:RO|UMERO)?\.?\s*)?[:#-]\s*(\d{5,})",
        ),
    )
    order_number_source = "document"
    if not order_number:
        order_number = _filename_order_hint(filename)
        order_number_source = "filename" if order_number else "missing"
    portal_reference = re.search(r"PEDIDOID=(\d+)", text, re.IGNORECASE)
    order_date = re.search(r"FECHA ELABORA:\s*(\d{2}/[A-Z]{3}/\d{4})", text, re.IGNORECASE)
    due_at = re.search(r"FECHA CANCELA:\s*(\d{2}/[A-Z]{3}/\d{4})", text, re.IGNORECASE)
    return [
        {
            "chain_name": "FAVORITA",
            "order_number": order_number,
            "order_number_source": order_number_source,
            "order_date": _iso_date(order_date.group(1) if order_date else None, ("%d/%b/%Y",)),
            "delivery_start_date": None,
            "delivery_due_date": _iso_date(due_at.group(1) if due_at else None, ("%d/%b/%Y",)),
            "destination": "CENTRO DE DISTRIBUCION",
            "external_reference": (
                f"PEDIDO PORTAL {portal_reference.group(1)}" if portal_reference else None
            ),
            "lines": rows,
        }
    ]


def _parse_rosado(text: str) -> list[dict[str, object]]:
    orders = []
    sections = re.split(r"CORPORACION EL ROSADO S\.\s*A\.", text, flags=re.IGNORECASE)
    line_pattern = re.compile(
        r"^\d+\s+\d+\s+(.+?)\s+((?:AE|AR)\d{3})\s+\S+\s+(6|12|288)\s+(\d+),00\s+",
        re.IGNORECASE,
    )
    for section in sections:
        order_match = re.search(r"NUMERO DE ORDEN\s+(\d+)", section, re.IGNORECASE)
        if not order_match:
            continue
        date_match = re.search(
            r"FECHA DEL\s+(\d{4}\.\d{2}\.\d{2})\s+FECHA DE\s+(\d{4}\.\d{2}\.\d{2})",
            section,
            re.IGNORECASE,
        )
        destination = re.search(r"PEDIDOS POR\s+(.+?)\s+FECHA DEL", section, re.IGNORECASE | re.DOTALL)
        rows = []
        for raw_line in section.splitlines():
            match = line_pattern.search(raw_line.strip())
            if not match:
                continue
            units_per_case = int(match.group(3))
            cases = int(match.group(4))
            rows.append(
                _line(
                    description=match.group(1),
                    requested_quantity=cases * units_per_case,
                    quantity_cases=cases,
                    units_per_case=units_per_case,
                    sku_hint=match.group(2).upper(),
                )
            )
        orders.append(
            {
                "chain_name": "ROSADO",
                "order_number": order_match.group(1),
                "order_number_source": "document",
                "order_date": _iso_date(date_match.group(1) if date_match else None, ("%Y.%m.%d",)),
                "delivery_start_date": None,
                "delivery_due_date": _iso_date(date_match.group(2) if date_match else None, ("%Y.%m.%d",)),
                "destination": " ".join(destination.group(1).split()) if destination else None,
                "external_reference": None,
                "lines": rows,
            }
        )
    return orders


_DANEC_CODES = {
    "1283410280001": "AR001",
    "1283410280002": "AR002",
    "1283410280003": "AE003",
    "1283410280004": "AR004",
}


def _parse_danec(text: str) -> list[dict[str, object]]:
    rows = []
    pattern = re.compile(r"^(\d+(?:\.\d+)?)\s+UN\s+(\d{13})\s+(.+?)\s+-\s+", re.IGNORECASE)
    for raw_line in text.splitlines():
        match = pattern.search(raw_line.strip())
        if not match:
            continue
        quantity = int(float(match.group(1)))
        supplier_code = match.group(2)
        sku = _DANEC_CODES.get(supplier_code)
        units_per_case_match = re.search(r"(6|12)U\b", match.group(3), re.IGNORECASE)
        units_per_case = int(units_per_case_match.group(1)) if units_per_case_match else 12
        rows.append(
            _line(
                description=match.group(3),
                requested_quantity=quantity,
                quantity_cases=quantity // units_per_case if quantity % units_per_case == 0 else None,
                units_per_case=units_per_case,
                sku_hint=sku,
                external_product_code=supplier_code,
            )
        )

    order_header = re.search(
        r"ORDEN\s+DE\s+COMPRA(.{0,35}?)\s+OB\b",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    order_number = ""
    if order_header:
        digits = "".join(re.findall(r"\d", order_header.group(1)))
        if len(digits) >= 6:
            order_number = digits
    order_date = re.search(r"FECHA DE ORDEN:\s*(\d{2}/\d{2}/\d{2})", text, re.IGNORECASE)
    due_at = re.search(r"FECHA DE ENTREGA:\s*(\d{2}/\d{2}/\d{2})", text, re.IGNORECASE)
    return [
        {
            "chain_name": "DANEC",
            "order_number": order_number,
            "order_number_source": "document" if order_number else "missing",
            "order_date": _iso_date(order_date.group(1) if order_date else None, ("%d/%m/%y",)),
            "delivery_start_date": None,
            "delivery_due_date": _iso_date(due_at.group(1) if due_at else None, ("%d/%m/%y",)),
            "destination": "BODEGA DE ENSAYOS",
            "external_reference": None,
            "lines": rows,
        }
    ]


def parse_purchase_order_pdf(filename: str, content: bytes) -> list[dict[str, object]]:
    if not filename.lower().endswith(".pdf"):
        raise PurchaseOrderFileError("Solo se permiten archivos PDF para detectar OCs.")
    if not content:
        raise PurchaseOrderFileError("El archivo PDF esta vacio.")

    try:
        with pdfplumber.open(BytesIO(content)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            upper = text.upper()
            if "TIENDAS INDUSTRIALES ASOCIADAS" in upper or "TIA S.A." in upper:
                orders = _parse_tia(pdf, text)
            elif "CORPORACION FAVORITA" in upper:
                orders = _parse_favorita(text, filename)
            elif "GERARDO ORTIZ" in upper:
                orders = _parse_gerardo_ortiz(text)
            elif "CORPORACION EL ROSADO" in upper:
                orders = _parse_rosado(text)
            elif "INDUSTRIAL DANEC" in upper:
                orders = _parse_danec(text)
            else:
                raise PurchaseOrderFileError("No pude identificar la cadena de esta OC.")
    except PurchaseOrderFileError:
        raise
    except Exception as exc:
        raise PurchaseOrderFileError("No se pudo leer el PDF de la OC.") from exc

    valid_orders = [order for order in orders if order.get("lines")]
    if not valid_orders:
        raise PurchaseOrderFileError(
            "No se detectaron productos en la OC. Revisa el archivo o registra la OC manualmente."
        )
    return valid_orders
