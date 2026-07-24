import asyncio
from datetime import datetime, timedelta

import httpx

from config import CRM_API_PREFIX, CRM_BASE_URL, CRM_PASSWORD, CRM_USERNAME

# Faqat GET so'rovlar — bot CRMga hech narsa yozmaydi/o'zgartirmaydi.

_token: str | None = None

MAX_GROUP_ID_SCAN = 150
GROUP_SCAN_CONCURRENCY = 10


class CRMError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _tashkent_now() -> datetime:
    return datetime.utcnow() + timedelta(hours=5)


def _url(path: str) -> str:
    return f"{CRM_BASE_URL}{CRM_API_PREFIX}{path}"


async def _login() -> str:
    global _token
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(
                _url("/auth/login"),
                json={"username": CRM_USERNAME, "password": CRM_PASSWORD},
            )
        except httpx.RequestError as error:
            raise CRMError(f"CRM bilan bog'lanib bo'lmadi: {error}") from error
    if resp.status_code != 200:
        raise CRMError(f"CRM login xato ({resp.status_code}): {resp.text[:200]}")
    _token = resp.json()["access_token"]
    return _token


async def _get(path: str, **kwargs):
    global _token
    if _token is None:
        await _login()
    for attempt in range(2):
        headers = {"Authorization": f"Bearer {_token}"}
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.get(_url(path), headers=headers, **kwargs)
            except httpx.RequestError as error:
                raise CRMError(f"CRM bilan bog'lanib bo'lmadi: {error}") from error
        if resp.status_code == 401 and attempt == 0:
            await _login()
            continue
        if resp.status_code >= 400:
            raise CRMError(f"CRM xatosi ({resp.status_code}): {resp.text[:200]}", status_code=resp.status_code)
        return resp.json()
    raise CRMError("CRM autentifikatsiyasi muvaffaqiyatsiz.")


async def get_groups() -> list[dict]:
    try:
        items: list[dict] = []
        page = 1
        while True:
            data = await _get("/groups", params={"is_active": True, "page_size": 100, "page": page})
            items.extend(data.get("items", []))
            meta = data.get("meta") or {}
            if page >= meta.get("total_pages", 1):
                break
            page += 1
        return items
    except CRMError as error:
        if error.status_code != 403:
            raise
        return await _scan_accessible_groups()


async def _scan_accessible_groups() -> list[dict]:
    """Fallback for roles (e.g. teacher) without bulk /groups access — probes
    /groups/{id} for each id, keeping only ones this account can see (their own)."""
    semaphore = asyncio.Semaphore(GROUP_SCAN_CONCURRENCY)

    async def _try(group_id: int) -> dict | None:
        async with semaphore:
            try:
                detail = await get_group_detail(group_id)
            except CRMError:
                return None
            return detail if detail.get("is_active", True) else None

    results = await asyncio.gather(*(_try(i) for i in range(1, MAX_GROUP_ID_SCAN + 1)))
    return [group for group in results if group is not None]


async def get_group_detail(group_id: int) -> dict:
    return await _get(f"/groups/{group_id}")


async def get_student(student_id: int) -> dict:
    return await _get(f"/students/{student_id}")


async def search_students(query: str, page_size: int = 20) -> list[dict]:
    """Guruhga bog'liq bo'lmagan holda, ism/telefon bo'yicha to'g'ridan-to'g'ri qidirish
    (guruhga hali qo'shilmagan o'quvchilarni ham topish uchun)."""
    data = await _get("/students", params={"search": query, "page_size": min(page_size, 100), "page": 1})
    return data.get("items", [])


async def get_payment_summary(student_id: int, month: int | None = None, year: int | None = None) -> dict:
    params = {}
    if month:
        params["month"] = month
    if year:
        params["year"] = year
    return await _get(f"/students/{student_id}/payments/summary", params=params)
