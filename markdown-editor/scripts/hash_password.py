#!/usr/bin/env python3
"""Generate a bcrypt hash for AUTH_PASSWORD_HASH.

Usage:
    python scripts/hash_password.py
"""
import getpass

import bcrypt


def main() -> None:
    password = getpass.getpass("Password to hash: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        raise SystemExit("Passwords did not match.")
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    print("\nAUTH_PASSWORD_HASH=" + hashed)


if __name__ == "__main__":
    main()
