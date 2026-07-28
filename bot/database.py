from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
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
    employees_columns = {
        row[1] for row in sync_conn.exec_driver_sql("PRAGMA table_info(employees)").fetchall()
    }
    if employees_columns and "is_superadmin" not in employees_columns:
        sync_conn.exec_driver_sql(
            "ALTER TABLE employees ADD COLUMN is_superadmin BOOLEAN NOT NULL DEFAULT 0"
        )

    roles_columns = {row[1] for row in sync_conn.exec_driver_sql("PRAGMA table_info(roles)").fetchall()}
    if roles_columns and "is_parent" not in roles_columns:
        sync_conn.exec_driver_sql("ALTER TABLE roles ADD COLUMN is_parent BOOLEAN NOT NULL DEFAULT 0")


def _migrate_parent_link_unique_constraint(sync_conn) -> None:
    """Bitta ota-ona bitta o'quvchiga faqat bir marta bog'lanishini bazada ham
    kafolatlaydi (avval faqat kod darajasida tekshirilardi)."""
    exists = sync_conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='parent_links'"
    ).fetchone()
    if exists is None:
        return
    sync_conn.exec_driver_sql(
        """
        DELETE FROM parent_links
        WHERE id NOT IN (SELECT MIN(id) FROM parent_links GROUP BY employee_id, crm_student_id)
        """
    )
    sync_conn.exec_driver_sql(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_parent_links_employee_student "
        "ON parent_links (employee_id, crm_student_id)"
    )


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)
        await conn.run_sync(_migrate_parent_link_unique_constraint)
