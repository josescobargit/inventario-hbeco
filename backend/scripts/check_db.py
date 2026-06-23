from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import engine  # noqa: E402


def main() -> None:
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version()")).scalar_one()
        products = conn.execute(text("SELECT COUNT(*) FROM products")).scalar_one()
        database_size_bytes = conn.execute(
            text("SELECT pg_database_size(current_database())")
        ).scalar_one()
    print("database=ok")
    print(f"version={version}")
    print(f"products={products}")
    print(f"database_size_bytes={database_size_bytes}")
    print(f"database_size_mb={database_size_bytes / 1024 / 1024:.2f}")


if __name__ == "__main__":
    main()
