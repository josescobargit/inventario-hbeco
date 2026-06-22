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
    print("database=ok")
    print(f"version={version}")
    print(f"products={products}")


if __name__ == "__main__":
    main()
