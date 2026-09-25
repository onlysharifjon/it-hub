"""Minar Space o'quvchi API'si — alohida servis sifatida (Docker: `space-api`).

CRM'ning to'liq ilovasini (seederlar, rejalashtiruvchilar) yuklamaydi; faqat `/space/...`
marshrutlari. Xodimlar API'si (`/space/admin/...`) CRM autentifikatsiyasiga bog'liq,
shuning uchun u `backend.main` ichida qoladi.

    uvicorn backend.space_app:app --workers 1   # bellashuv xonalari xotirada — bitta jarayon
"""
from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

import fastapi.encoders as _fastapi_encoders  # noqa: E402
from datetime import datetime  # noqa: E402

from . import tz  # noqa: E402
from .minar import setup  # noqa: E402

# main.py dagi kabi: API javoblaridagi datetime'lar Toshkent offseti bilan
_fastapi_encoders.ENCODERS_BY_TYPE[datetime] = tz.isoformat

app = FastAPI(title="Minar Space API", docs_url=None, redoc_url=None, openapi_url=None)
setup(app, student=True, admin=False)


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"ok": True}
