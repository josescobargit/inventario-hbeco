from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.dialects.postgresql import insert  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models.inventory import Product, StockPosition  # noqa: E402


DEFAULT_INPUT = ROOT / "database" / "seed_data" / "products_seed.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load product seed CSV into PostgreSQL.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    return parser.parse_args()


def load_products(input_path: Path) -> int:
    with input_path.open(encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    with SessionLocal() as session:
        for row in rows:
            values = {
                "sku": row["sku"],
                "name": row["name"],
                "description": row["description"] or None,
                "category": row["category"] or None,
                "barcode": row["barcode"] or None,
                "contifico_aux_code": row["contifico_aux_code"] or None,
                "cost": row["cost"],
                "units_per_case": int(row["units_per_case"]),
                "is_active": row["is_active"].lower() == "true",
            }
            statement = insert(Product).values(**values)
            statement = statement.on_conflict_do_update(
                index_elements=[Product.sku],
                set_={
                    "name": statement.excluded.name,
                    "description": statement.excluded.description,
                    "category": statement.excluded.category,
                    "barcode": statement.excluded.barcode,
                    "contifico_aux_code": statement.excluded.contifico_aux_code,
                    "cost": statement.excluded.cost,
                    "units_per_case": statement.excluded.units_per_case,
                    "is_active": statement.excluded.is_active,
                },
            )
            session.execute(statement)

        session.flush()

        products = session.scalars(select(Product)).all()
        for product in products:
            statement = insert(StockPosition).values(product_id=product.id)
            statement = statement.on_conflict_do_nothing(index_elements=[StockPosition.product_id])
            session.execute(statement)

        session.commit()
    return len(rows)


def main() -> None:
    args = parse_args()
    count = load_products(args.input)
    print(f"loaded_products={count}")
    print("initial_stock_positions=created_with_zero_operational_stock")


if __name__ == "__main__":
    main()
