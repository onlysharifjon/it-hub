#!/usr/bin/env python3
"""Provision a new Paycom certification database and private container env.

Run on the server only after the test cashbox's merchant ID and *test_key* have
been saved in root-readable files. This script never reads the live CRM env,
never prints a key/password, and refuses to reuse an existing role/database.
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import stat
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote


DB_NAME = "paycom_sandbox"
DB_ROLE = "paycom_sandbox_role"
ENV_PATH = Path("/var/www/minar-stack/env/paycom-sandbox.env")
SAFE_TOKEN = re.compile(r"[A-Za-z0-9_-]+\Z")
SAFE_HOST = re.compile(r"[A-Za-z0-9_.-]+\Z")


class ProvisionError(Exception):
    pass


def _private_token_file(path: Path, label: str) -> str:
    if not path.is_absolute() or path.is_symlink():
        raise ProvisionError(f"{label} must be an absolute, non-symlink file")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise ProvisionError(f"{label} must be a regular file with mode 0600")
    value = path.read_text(encoding="utf-8").strip()
    if not value or not SAFE_TOKEN.fullmatch(value):
        raise ProvisionError(f"{label} contains unsupported characters or is empty")
    return value


def _psql(container: str, user: str, sql: str) -> str:
    # SQL is sent on stdin, so the generated password never appears in argv,
    # shell history, a Docker command line, or normal psql output.
    process = subprocess.run(
        ["docker", "exec", "-i", container, "psql", "-X", "-q", "-t", "-A",
         "-v", "ON_ERROR_STOP=1", "-U", user, "-d", "postgres"],
        input=sql, text=True, capture_output=True, check=False,
    )
    if process.returncode:
        # psql can echo a failing SQL statement, including a password. Never
        # forward stdout/stderr for a statement containing credentials.
        raise ProvisionError("PostgreSQL command failed; inspect server logs privately")
    return process.stdout.strip()


def _write_env(path: Path, db_host: str, merchant_id: str, test_key: str,
               db_password: str) -> None:
    if path.exists() or path.is_symlink():
        raise ProvisionError(f"Refusing to overwrite {path}")
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise ProvisionError(f"Private env directory is missing: {path.parent}")
    db_url = (f"postgresql://{DB_ROLE}:{quote(db_password, safe='')}@"
              f"{db_host}:5432/{DB_NAME}")
    values = {
        "DATABASE_URL": db_url,
        "PAYCOM_SANDBOX_MODE": "enabled",
        "PAYME_ACCOUNT_FIELD": "order_id",
        "PAYME_MERCHANT_ID": merchant_id,
        "PAYME_KEY": test_key,
        "PAYME_CHECKOUT_URL": "https://checkout.test.paycom.uz",
        "PAYMENT_ALLOW_REFUND": "true",
        "PARENT_PAYMENTS_ENABLED": "false",
        "SCHEDULERS_ENABLED": "false",
        "SECRET_KEY": secrets.token_urlsafe(48),
    }
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            for name, value in values.items():
                output.write(f"{name}={value}\n")
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def provision(container: str, pg_user: str, db_host: str,
              merchant_id_file: Path, test_key_file: Path) -> None:
    for label, value in (("container", container), ("PostgreSQL user", pg_user)):
        if not SAFE_TOKEN.fullmatch(value):
            raise ProvisionError(f"Invalid {label}")
    if not SAFE_HOST.fullmatch(db_host) or db_host in {"localhost", "127.0.0.1"}:
        raise ProvisionError("Database host must be the Docker-network service name")
    if os.geteuid() != 0:
        raise ProvisionError("Run as root to protect the sandbox env file")
    if ENV_PATH.exists() or ENV_PATH.is_symlink():
        raise ProvisionError(f"Refusing to overwrite {ENV_PATH}")
    if ENV_PATH.parent.is_symlink() or not ENV_PATH.parent.is_dir():
        raise ProvisionError(f"Private env directory is missing: {ENV_PATH.parent}")
    merchant_id = _private_token_file(merchant_id_file, "test merchant ID")
    test_key = _private_token_file(test_key_file, "Paycom test_key")
    exists = _psql(container, pg_user,
                   f"SELECT (SELECT COUNT(*) FROM pg_roles WHERE rolname = '{DB_ROLE}'),"
                   f" (SELECT COUNT(*) FROM pg_database WHERE datname = '{DB_NAME}');")
    if exists != "0|0":
        raise ProvisionError("Dedicated sandbox role or database already exists; refusing to reuse it")

    db_password = secrets.token_urlsafe(48)
    # Store credentials first. If provisioning fails, the file remains private
    # and a human can inspect/recover the partial *sandbox-only* setup.
    _write_env(ENV_PATH, db_host, merchant_id, test_key, db_password)
    try:
        _psql(container, pg_user,
              f"CREATE ROLE {DB_ROLE} LOGIN PASSWORD '{db_password}' "
              "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;")
        _psql(container, pg_user,
              f"CREATE DATABASE {DB_NAME} OWNER {DB_ROLE} "
              "TEMPLATE template0 ENCODING 'UTF8';")
        _psql(container, pg_user,
              f"REVOKE CONNECT ON DATABASE {DB_NAME} FROM PUBLIC;")
    except ProvisionError as exc:
        raise ProvisionError(
            f"{exc}; sandbox provisioning may be partial. "
            f"Private credentials remain at {ENV_PATH}; do not rerun blindly"
        ) from exc
    print(f"Created isolated {DB_NAME} role/database and private {ENV_PATH} (mode 0600)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-container", required=True,
                        help="Exact running PostgreSQL container name")
    parser.add_argument("--pg-user", required=True,
                        help="PostgreSQL superuser inside that container")
    parser.add_argument("--db-host", required=True,
                        help="PostgreSQL Docker service hostname, e.g. db")
    parser.add_argument("--merchant-id-file", type=Path, required=True)
    parser.add_argument("--test-key-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        provision(args.db_container, args.pg_user, args.db_host,
                  args.merchant_id_file, args.test_key_file)
    except (ProvisionError, OSError) as exc:
        print(f"Provisioning stopped: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
