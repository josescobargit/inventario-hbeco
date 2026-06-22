from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.catalog import (  # noqa: E402
    ProductSeed,
    clean_catalog_code,
    clean_decimal,
    clean_text,
    is_product_sku,
    units_per_case_for_product,
)


DEFAULT_INPUT = Path("/Users/joseescobar/Downloads/PRODUCTOS HOME .xlsx")
DEFAULT_OUTPUT = ROOT / "database" / "seed_data" / "products_seed.csv"
SHEET_NAME = "Productos1"
HEADER_ROW = 3
FIELDNAMES = [
    "sku",
    "name",
    "description",
    "category",
    "barcode",
    "contifico_aux_code",
    "cost",
    "units_per_case",
    "is_active",
]


def read_products(path: Path) -> list[ProductSeed]:
    df = pd.read_excel(path, sheet_name=SHEET_NAME, header=HEADER_ROW)
    df = df.dropna(how="all")
    df.columns = [clean_text(c) for c in df.columns]

    rows: list[ProductSeed] = []
    seen: set[str] = set()
    for _, row in df.iterrows():
        sku = clean_text(row.get("Codigo") or row.get("Código")).upper()
        if not is_product_sku(sku) or sku in seen:
            continue
        seen.add(sku)

        name = clean_text(row.get("Nombre"))
        description = clean_text(row.get("Descripcion") or row.get("Descripción"))
        category = clean_text(row.get("Categoria") or row.get("Categoría"))
        aux_code = clean_catalog_code(row.get("Codigo Auxiliar") or row.get("Código Auxiliar"))
        barcode = clean_catalog_code(row.get("Codigo Catalogo") or row.get("Código Catálogo"))
        cost = clean_decimal(row.get("Costo"))
        units_per_case = units_per_case_for_product(sku, name, description)

        rows.append(
            ProductSeed(
                sku=sku,
                name=name,
                description=description,
                category=category,
                barcode=barcode,
                contifico_aux_code=aux_code,
                cost=cost,
                units_per_case=units_per_case,
            )
        )
    return rows


def write_csv(products: list[ProductSeed], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        for product in products:
            writer.writerow(
                {
                    "sku": product.sku,
                    "name": product.name,
                    "description": product.description,
                    "category": product.category,
                    "barcode": product.barcode,
                    "contifico_aux_code": product.contifico_aux_code,
                    "cost": f"{product.cost:.4f}",
                    "units_per_case": product.units_per_case,
                    "is_active": str(product.is_active).lower(),
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build product seed CSV from Contifico export.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    products = read_products(args.input)
    write_csv(products, args.output)
    print(f"products={len(products)}")
    print(f"output={args.output}")
    print("stock_from_contifico=ignored")


if __name__ == "__main__":
    main()
