"""Minar Space (space.minaracademy.uz) — o'quvchi kabineti API'si.

CRM bilan bir jarayon va bir baza. Frontend shartnomasi: minar-academy/API-CONTRACT.md,
endpointlar ro'yxati: minar-academy/docs/API-LIST.md.

`backend/main.py` oxirida `setup(app)` chaqiriladi:
  * `/space/...`        — o'quvchi API'si (nginx: space.minaracademy.uz/api/ -> shu prefiks, WebSocket ham)
  * `/space/admin/...`  — xodimlar API'si (faqat CRM domeni orqali; space domenida nginx 404 qaytaradi)
"""


def setup(app) -> None:
    from .errors import MinarError, minar_error_handler
    from . import models  # noqa: F401  (jadvallar Base.metadata ga qo'shilsin)
    from .admin import router as admin_router
    from .router import router as student_router

    app.add_exception_handler(MinarError, minar_error_handler)
    app.include_router(student_router, prefix="/space", tags=["space"])
    app.include_router(admin_router, prefix="/space/admin", tags=["space-admin"])
