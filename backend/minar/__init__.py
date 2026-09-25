"""Minar Space (space.minaracademy.uz) — o'quvchi kabineti API'si.

CRM bilan bir jarayon va bir baza. Frontend shartnomasi: minar-academy/API-CONTRACT.md,
endpointlar ro'yxati: minar-academy/docs/API-LIST.md.

`backend/main.py` oxirida `setup(app)` chaqiriladi:
  * `/space/...`        — o'quvchi API'si (nginx: space.minaracademy.uz/api/ -> shu prefiks, WebSocket ham)
  * `/space/admin/...`  — xodimlar API'si (faqat CRM domeni orqali; space domenida nginx 404 qaytaradi)
"""


def setup(app, *, student: bool | None = None, admin: bool = True) -> None:
    """`student=None` — `MINAR_STUDENT_API` env'dan (default "true").

    Docker'da o'quvchi API'si alohida `space-api` servisida (backend/space_app.py) ishlaydi,
    CRM konteyneri esa `MINAR_STUDENT_API=false` bilan faqat xodimlar API'sini ulaydi —
    bellashuv xonalari xotirada, shuning uchun ular bitta jarayonda qolishi shart.
    """
    import os

    from .errors import MinarError, minar_error_handler
    from . import models  # noqa: F401  (jadvallar Base.metadata ga qo'shilsin)

    if student is None:
        student = os.getenv("MINAR_STUDENT_API", "true").lower() != "false"

    app.add_exception_handler(MinarError, minar_error_handler)
    if student:
        from .router import router as student_router
        app.include_router(student_router, prefix="/space", tags=["space"])
    if admin:
        from .admin import router as admin_router
        app.include_router(admin_router, prefix="/space/admin", tags=["space-admin"])
