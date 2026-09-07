"""Vaqt zonasi kelishuvini qulflaydigan testlar.

Bu yerdagi har bir test ilgari haqiqatan sodir bo'lgan xatoni qaytib
kelishidan saqlaydi: server UTC'da ishlagani uchun Toshkent bo'yicha
00:00–05:00 orasida "bugun" bir kun orqada qolar, sana filtrlari esa
5 soatga siljib, tunda kiritilgan yozuvlarni boshqa kunga qo'shardi.
"""
from datetime import date, datetime

from backend import tz


def test_now_is_five_hours_ahead_of_utc():
    delta = tz.now() - tz.utcnow()
    assert abs(delta.total_seconds() - 5 * 3600) < 2


def test_today_uses_tashkent_calendar():
    # UTC bo'yicha 6-sentyabr 20:00 — Toshkentda allaqachon 7-sentyabr.
    assert tz.to_local(datetime(2026, 9, 6, 20, 0)).date() == date(2026, 9, 7)


def test_process_timezone_is_installed():
    """`date.today()` / `datetime.now()` ham Toshkentni ko'rsatishi kerak."""
    assert date.today() == tz.today()
    assert abs((datetime.now() - tz.now()).total_seconds()) < 2


def test_day_bounds_cover_the_tashkent_day_in_utc():
    start, end = tz.day_bounds(date(2026, 9, 7))
    assert start == datetime(2026, 9, 6, 19, 0)
    assert end == datetime(2026, 9, 7, 19, 0)
    # Toshkentda 7-sentyabr 02:00 da yozilgan yozuv shu kunga tushadi.
    assert start <= tz.to_utc(datetime(2026, 9, 7, 2, 0)) < end


def test_month_bounds_cover_the_tashkent_month_in_utc():
    start, end = tz.month_bounds(2026, 12)
    assert start == datetime(2026, 11, 30, 19, 0)
    assert end == datetime(2026, 12, 31, 19, 0)


def test_isoformat_carries_the_tashkent_offset():
    assert tz.isoformat(datetime(2026, 9, 7, 9, 11)) == "2026-09-07T14:11:00+05:00"


def test_local_utc_roundtrip():
    local = datetime(2026, 9, 7, 14, 11)
    assert tz.to_local(tz.to_utc(local)) == local
