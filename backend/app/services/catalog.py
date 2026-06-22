from __future__ import annotations

import math
import re
from dataclasses import dataclass


SKU_PATTERN = re.compile(r"^[A-Z]{2,4}\d{3}$")


@dataclass(frozen=True)
class ProductSeed:
    sku: str
    name: str
    description: str
    category: str
    barcode: str
    contifico_aux_code: str
    cost: float
    units_per_case: int
    is_active: bool = True


def clean_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def clean_decimal(value: object) -> float:
    text = clean_text(value)
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def clean_catalog_code(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def is_product_sku(value: object) -> bool:
    return bool(SKU_PATTERN.match(clean_text(value).upper()))


def units_per_case_for_product(sku: str, name: str, description: str = "") -> int:
    text = f"{sku} {name} {description}".upper()
    if sku.upper() in {"AR005", "AR006"} or "SACHET" in text or "RISTRA" in text or "18 ML" in text:
        return 288
    if "PACK" in text:
        return 6
    return 12
