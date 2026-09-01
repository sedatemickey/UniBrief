"""Interactive administrator credential initialization command."""

from __future__ import annotations

import argparse
from getpass import getpass

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.services.setting_service import get_int_setting, get_raw_setting, set_setting


def _read_confirmed_password() -> str:
    password = getpass("New administrator password: ")
    confirmation = getpass("Confirm administrator password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    if not 10 <= len(password) <= 128:
        raise SystemExit("Administrator password must contain 10 to 128 characters.")
    return password


def set_admin_password(*, require_uninitialized: bool) -> None:
    """Initialize or reset the administrator password without command-line secrets."""

    password = _read_confirmed_password()
    with SessionLocal() as db:
        existing = get_raw_setting(db, "admin_password_hash")
        if require_uninitialized and existing is not None:
            raise SystemExit("Administrator password is already initialized; use reset-password.")
        set_setting(db, "admin_password_hash", hash_password(password))
        version = get_int_setting(db, "admin_session_version")
        set_setting(db, "admin_session_version", version + 1)
        db.commit()
    print("Administrator password updated; existing admin sessions were revoked.")


def main() -> int:
    """Dispatch the safe interactive administrator CLI."""

    parser = argparse.ArgumentParser(prog="python -m app.cli.admin")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init-password")
    subparsers.add_parser("reset-password")
    args = parser.parse_args()
    set_admin_password(require_uninitialized=args.command == "init-password")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
