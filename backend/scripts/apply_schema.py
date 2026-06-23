from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

def main() -> None:
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    print("database_schema=head")


if __name__ == "__main__":
    main()
