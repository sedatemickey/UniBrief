"""Validate the configured MySQL connection without printing credentials."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import check_database, create_database_engine  # noqa: E402


def main() -> int:
    """Connect to MySQL and print only non-sensitive environment properties."""

    engine = create_database_engine()
    try:
        status = check_database(engine)
    finally:
        engine.dispose()
    print(json.dumps({"status": "ok", **status.as_dict()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
