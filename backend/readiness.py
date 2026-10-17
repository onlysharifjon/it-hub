"""Liveness is process-only; readiness verifies dependencies and fails closed."""
from fastapi.responses import JSONResponse
from sqlalchemy import text
from .database import SessionLocal
from . import security


def check():
    status={'database':False,'redis':not bool(security.REDIS_URL)}
    db=SessionLocal()
    try:
        db.execute(text('SELECT 1'));status['database']=True
    except Exception:
        pass
    finally:
        db.close()
    if security.REDIS_URL:
        try:
            r=security._get_redis();status['redis']=bool(r and r.ping())
        except Exception:
            pass
    ok=all(status.values())
    return JSONResponse({'ok':ok,'checks':status},status_code=200 if ok else 503)
