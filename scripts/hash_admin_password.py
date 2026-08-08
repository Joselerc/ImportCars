"""Generate an Argon2id password hash without echoing the password."""

from __future__ import annotations

from getpass import getpass

from import_cars.services.admin_auth import hash_admin_password


def main() -> None:
    password = getpass("Contraseña del administrador: ")
    confirmation = getpass("Repite la contraseña: ")
    if password != confirmation:
        raise SystemExit("Las contraseñas no coinciden.")
    print(hash_admin_password(password))


if __name__ == "__main__":
    main()
