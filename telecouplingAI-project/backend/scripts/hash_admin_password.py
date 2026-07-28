"""Generate an Argon2id hash for ADMIN_PASSWORD_HASH."""
from __future__ import annotations

import getpass

from argon2 import PasswordHasher


def main() -> None:
    password = getpass.getpass("Admin password: ")
    confirmation = getpass.getpass("Confirm admin password: ")
    if not password:
        raise SystemExit("Password must not be empty")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    print(PasswordHasher().hash(password))


if __name__ == "__main__":
    main()
