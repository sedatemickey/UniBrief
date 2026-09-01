"""Run the default-disabled NapCat OneBot 11 bridge for one normal user."""

from __future__ import annotations

import asyncio
import logging
import sys
from getpass import getpass
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))

from app.adapters.napcat import NapCatBridge  # noqa: E402
from app.core.config import get_settings  # noqa: E402


def main() -> int:
    """Read the password from a Secret or prompt and run until interrupted."""

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    if not settings.napcat_enabled:
        print("NAPCAT_ENABLED=false; bridge was not started.")
        return 0
    password = settings.unibrief_password or getpass("UniBrief user password: ")
    try:
        asyncio.run(NapCatBridge(password, settings).run())
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
