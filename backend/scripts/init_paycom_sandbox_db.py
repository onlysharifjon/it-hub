"""Initialize only a brand-new, isolated Paycom certification database.

The full CRM Alembic chain is not suitable for a fresh certification DB: an
existing revision exceeds Alembic's 32-character version column. The sandbox
is disposable, so install the current model schema and only the finance system
rows that Paycom Perform/Cancel requires. Refuse any nonempty database.
"""

from __future__ import annotations

from backend.paycom_sandbox_app import ensure_auth_table, require_sandbox_database

require_sandbox_database()

from sqlalchemy import inspect  # noqa: E402

from backend import models  # noqa: E402,F401  -- register current model tables
from backend.database import Base, SessionLocal, engine  # noqa: E402
from backend.finance.service import ensure_system_rows  # noqa: E402


def initialize() -> None:
    existing = inspect(engine).get_table_names()
    if existing:
        raise RuntimeError("Sandbox database is not empty; refusing to change existing tables")
    Base.metadata.create_all(bind=engine)
    with SessionLocal.begin() as db:
        ensure_system_rows(db)
    ensure_auth_table()
    print("Paycom sandbox schema, finance accounts, and test credential initialized")


if __name__ == "__main__":
    initialize()
