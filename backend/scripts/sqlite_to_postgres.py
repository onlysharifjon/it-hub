"""SQLite (ithub.db) -> PostgreSQL ko'chirish.

    python -m backend.scripts.sqlite_to_postgres SRC_SQLITE_URL DST_POSTGRES_URL [--replace]

- Sxema modellar (`Base.metadata`) bo'yicha yaratiladi, keyin `alembic stamp heads` qilinadi
  (SQLite bazasi alembic head'da bo'lishi shart — tekshiriladi).
- Ma'lumotlar jadvalma-jadval, modelning ustun turlari orqali o'qiladi (SQLite'dagi 0/1, matnli
  sanalar to'g'ri Python turlariga aylanadi) va FK tekshiruvi vaqtincha o'chirilgan holda yoziladi.
- Serial ketma-ketliklar (id) MAX(id) ga suriladi, oxirida har jadvalda qatorlar soni solishtiriladi.
- Maqsad bazada jadvallar bo'lsa — `--replace`siz to'xtaydi.
"""
from __future__ import annotations

import subprocess
import sys

from sqlalchemy import MetaData, Table, create_engine, func, inspect, select, text

BATCH = 1000


def main(src_url: str, dst_url: str, replace: bool) -> None:
    import os
    os.environ["DATABASE_URL"] = dst_url            # backend.database import qilinishidan oldin
    from backend.database import Base
    from backend import models  # noqa: F401
    from backend.minar import models as _minar_models  # noqa: F401

    src = create_engine(src_url)
    dst = create_engine(dst_url)

    with src.connect() as c:
        src_rev = {r[0] for r in c.exec_driver_sql("SELECT version_num FROM alembic_version")}
    heads = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "heads"],
        capture_output=True, text=True, check=True,
    ).stdout
    head_revs = {line.split()[0] for line in heads.splitlines() if line.strip()}
    if src_rev != head_revs:
        sys.exit(f"SQLite alembic reviziyasi {src_rev} head {head_revs} bilan mos emas — avval upgrade qiling")

    src_tables = set(inspect(src).get_table_names())
    model_tables = [t for t in Base.metadata.sorted_tables]
    extra = sorted(src_tables - {t.name for t in model_tables} - {"alembic_version"})
    if extra:
        print(f"  Modelda yo'q jadvallar (boshqa branch'lardan) — sxemasi SQLite'dan olinib ko'chiriladi: {extra}")

    existing = set(inspect(dst).get_table_names())
    if existing:
        if not replace:
            sys.exit(f"Maqsad bazada {len(existing)} ta jadval bor — --replace bilan qayta ishga tushiring")
        with dst.begin() as c:
            c.exec_driver_sql("DROP SCHEMA public CASCADE; CREATE SCHEMA public")

    Base.metadata.create_all(dst)

    # Modelda yo'q jadvallar: SQLite'dagi sxemani aks ettirib (reflection) yaratamiz
    extra_meta = MetaData()
    for name in extra:
        t = Table(name, extra_meta, autoload_with=src)
        for col in t.columns:
            col.type = col.type.as_generic()    # SQLite DATETIME -> umumiy DateTime (PG: TIMESTAMP)
    extra_meta.create_all(dst)
    all_tables = model_tables + [extra_meta.tables[n] for n in extra]

    src_cols = {t: {c["name"] for c in inspect(src).get_columns(t)} for t in src_tables}
    counts: dict[str, int] = {}
    with src.connect() as s, dst.begin() as d:
        d.exec_driver_sql("SET session_replication_role = replica")   # FK tekshiruvi yuklash davomida o'chiq
        for table in all_tables:
            if table.name not in src_tables:
                print(f"  {table.name}: SQLite'da yo'q — bo'sh qoladi")
                counts[table.name] = 0
                continue
            cols = [c for c in table.columns if c.name in src_cols[table.name]]
            missing = [c.name for c in table.columns if c.name not in src_cols[table.name]]
            if missing:
                print(f"  {table.name}: SQLite'da yo'q ustunlar (default qo'llanadi): {missing}")
            n = 0
            result = s.execute(select(*cols)).yield_per(BATCH)
            for part in result.partitions(BATCH):
                rows = [dict(zip((c.name for c in cols), r)) for r in part]
                d.execute(table.insert(), rows)
                n += len(rows)
            counts[table.name] = n
        d.exec_driver_sql("SET session_replication_role = DEFAULT")

        # id ketma-ketliklari
        for table in all_tables:
            for col in table.primary_key.columns:
                seq = d.execute(text("SELECT pg_get_serial_sequence(:t, :c)"),
                                {"t": table.name, "c": col.name}).scalar()
                if seq:
                    d.execute(text(f'SELECT setval(:s, COALESCE((SELECT MAX("{col.name}") FROM "{table.name}"), 1), '
                                   f'(SELECT MAX("{col.name}") FROM "{table.name}") IS NOT NULL)'), {"s": seq})

    subprocess.run([sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "stamp", "heads"],
                   check=True, env={**os.environ, "DATABASE_URL": dst_url}, capture_output=True)

    # Tekshiruv
    bad = []
    with src.connect() as s, dst.connect() as d:
        for table in all_tables:
            if table.name not in src_tables:
                continue
            a = s.execute(select(func.count()).select_from(table)).scalar()
            b = d.execute(select(func.count()).select_from(table)).scalar()
            if a != b:
                bad.append(f"{table.name}: sqlite={a} pg={b}")
    total = sum(counts.values())
    print(f"Ko'chirildi: {len(counts)} jadval, {total} qator")
    if bad:
        sys.exit("QATORLAR SONI MOS EMAS:\n  " + "\n  ".join(bad))
    print("Tekshiruv: barcha jadvallarda qatorlar soni mos")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        sys.exit(__doc__)
    main(args[0], args[1], "--replace" in sys.argv)
