from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import engine  # noqa: E402


SCHEMA_PATH = ROOT / "database" / "schema" / "001_initial_schema.sql"


def split_sql_statements(sql: str) -> list[str]:
    return [statement.strip() for statement in sql.split(";") if statement.strip()]


def main() -> None:
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    statements = split_sql_statements(sql)
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
    print(f"applied_schema={SCHEMA_PATH}")
    print(f"statements={len(statements)}")


if __name__ == "__main__":
    main()
