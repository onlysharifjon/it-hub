from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import DATABASE_URL


class Base(DeclarativeBase):
    pass


engine = create_async_engine(DATABASE_URL)
async_session = async_sessionmaker(engine, expire_on_commit=False)


def _add_missing_columns(sync_conn) -> None:
    inspector_columns = {
        row[1] for row in sync_conn.exec_driver_sql("PRAGMA table_info(fines)").fetchall()
    }
    if inspector_columns and "reason" not in inspector_columns:
        sync_conn.exec_driver_sql("ALTER TABLE fines ADD COLUMN reason VARCHAR(255) NOT NULL DEFAULT ''")


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)
