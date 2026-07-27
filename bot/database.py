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

    fines_columns = {row[1] for row in sync_conn.exec_driver_sql("PRAGMA table_info(fines)").fetchall()}
    if fines_columns and "reason" not in fines_columns:
        sync_conn.exec_driver_sql("ALTER TABLE fines ADD COLUMN reason VARCHAR(255) NOT NULL DEFAULT ''")
    if fines_columns and "severity" not in fines_columns:
        sync_conn.exec_driver_sql("ALTER TABLE fines ADD COLUMN severity VARCHAR(16)")
    if fines_columns and "code" not in fines_columns:
        sync_conn.exec_driver_sql("ALTER TABLE fines ADD COLUMN code VARCHAR(16)")
    if fines_columns and "cancelled_at" not in fines_columns:
        sync_conn.exec_driver_sql("ALTER TABLE fines ADD COLUMN cancelled_at DATETIME")
    if fines_columns and "cancelled_by_id" not in fines_columns:
        sync_conn.exec_driver_sql("ALTER TABLE fines ADD COLUMN cancelled_by_id INTEGER")

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


def _index_columns_map(sync_conn, table: str) -> dict[str, list[str]]:
    indexes = sync_conn.exec_driver_sql(f"PRAGMA index_list('{table}')").fetchall()
    result: dict[str, list[str]] = {}
    for idx in indexes:
        idx_name, is_unique = idx[1], idx[2]
        if not is_unique:
            continue
        cols = sync_conn.exec_driver_sql(f"PRAGMA index_info('{idx_name}')").fetchall()
        result[idx_name] = [c[2] for c in cols]
    return result


def _migrate_fine_template_unique_constraint(sync_conn) -> None:
    """text ustunidagi eski GLOBAL unique cheklovni (owner, text) kompozit
    cheklovga almashtiradi — admin va audit endi bir xil matnli shablonlarga
    ega bo'lishi mumkin. SQLite ustun darajasidagi UNIQUE'ni to'g'ridan-to'g'ri
    o'chira olmaydi, shuning uchun jadval qayta yaratiladi."""
    exists = sync_conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='fine_templates'"
    ).fetchone()
    if exists is None:
        return
    indexes = _index_columns_map(sync_conn, "fine_templates")
    has_owner_text = any(cols == ["owner", "text"] for cols in indexes.values())
    has_standalone_text = any(cols == ["text"] for cols in indexes.values())
    if has_owner_text or not has_standalone_text:
        return
    sync_conn.exec_driver_sql("ALTER TABLE fine_templates RENAME TO fine_templates_old")
    sync_conn.exec_driver_sql(
        """
        CREATE TABLE fine_templates (
            id INTEGER PRIMARY KEY,
            text VARCHAR(255) NOT NULL,
            short_name VARCHAR(64) NOT NULL,
            owner VARCHAR(16) NOT NULL,
            shared_with_audit BOOLEAN NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME,
            code VARCHAR(16),
            severity VARCHAR(16),
            CONSTRAINT uq_fine_templates_owner_text UNIQUE (owner, text)
        )
        """
    )
    sync_conn.exec_driver_sql(
        """
        INSERT INTO fine_templates
            (id, text, short_name, owner, shared_with_audit, is_active, created_at, code, severity)
        SELECT id, text, short_name, owner, shared_with_audit, is_active, created_at, code, severity
        FROM fine_templates_old
        """
    )
    sync_conn.exec_driver_sql("DROP TABLE fine_templates_old")


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
        await conn.run_sync(_migrate_fine_template_unique_constraint)
        await conn.run_sync(_migrate_parent_link_unique_constraint)
