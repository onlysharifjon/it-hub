from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import DATABASE_URL


class Base(DeclarativeBase):
    pass


engine = create_async_engine(DATABASE_URL)
async_session = async_sessionmaker(engine, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _record) -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def _add_missing_columns(sync_conn) -> None:
    fines_columns = {row[1] for row in sync_conn.exec_driver_sql("PRAGMA table_info(fines)").fetchall()}
    if fines_columns and "reason" not in fines_columns:
        sync_conn.exec_driver_sql("ALTER TABLE fines ADD COLUMN reason VARCHAR(255) NOT NULL DEFAULT ''")
    if fines_columns and "severity" not in fines_columns:
        sync_conn.exec_driver_sql("ALTER TABLE fines ADD COLUMN severity VARCHAR(16)")

    roles_columns = {row[1] for row in sync_conn.exec_driver_sql("PRAGMA table_info(roles)").fetchall()}
    if roles_columns and "is_parent" not in roles_columns:
        sync_conn.exec_driver_sql("ALTER TABLE roles ADD COLUMN is_parent BOOLEAN NOT NULL DEFAULT 0")

    template_columns = {
        row[1] for row in sync_conn.exec_driver_sql("PRAGMA table_info(fine_templates)").fetchall()
    }
    if template_columns:
        if "short_name" not in template_columns:
            sync_conn.exec_driver_sql(
                "ALTER TABLE fine_templates ADD COLUMN short_name VARCHAR(64) NOT NULL DEFAULT ''"
            )
            sync_conn.exec_driver_sql(
                "UPDATE fine_templates SET short_name = substr(text, 1, 24) WHERE short_name = ''"
            )
        if "owner" not in template_columns:
            sync_conn.exec_driver_sql(
                "ALTER TABLE fine_templates ADD COLUMN owner VARCHAR(16) NOT NULL DEFAULT 'admin'"
            )
        if "shared_with_audit" not in template_columns:
            sync_conn.exec_driver_sql(
                "ALTER TABLE fine_templates ADD COLUMN shared_with_audit BOOLEAN NOT NULL DEFAULT 0"
            )
        if "code" not in template_columns:
            sync_conn.exec_driver_sql("ALTER TABLE fine_templates ADD COLUMN code VARCHAR(16)")
        if "severity" not in template_columns:
            sync_conn.exec_driver_sql("ALTER TABLE fine_templates ADD COLUMN severity VARCHAR(16)")


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)
