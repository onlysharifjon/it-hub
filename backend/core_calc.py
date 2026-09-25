"""To'lov / qarz hisobining yagona manbai (single source of truth).

Ham CRM (main.py), ham ota-ona API (parent/) shu funksiyalardan foydalanadi —
mantiq ikki joyda takrorlanmasligi uchun.
"""
from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from . import models, tz

ZERO = Decimal("0")


def active_special_discounts(db: Session, student_id: int) -> list:
    """Talabaning aktiv Special chegirmalari."""
    return (
        db.query(models.SpecialDiscount)
        .filter(
            models.SpecialDiscount.student_id == student_id,
            models.SpecialDiscount.is_active == True,
        )
        .all()
    )


def apply_special_discounts(price: Decimal, discounts: list, group_id: int,
                            month: int = None, year: int = None, apply_global: bool = True,
                            active_group_ids: Optional[set] = None) -> Decimal:
    """Special chegirmalarni narxga qo'llaydi.

    - free_month: month/year mos kelsa oy to'liq bepul (0).
    - monthly:    har oy amount so'm ayiriladi (butun kurs davomida).
    - one_time:   month/year mos kelsa faqat o'sha oy uchun amount so'm ayiriladi.
    group_id NULL bo'lgan chegirma barcha guruhlarga tegishli — lekin talaba
    bir nechta guruhda bo'lsa, bu funksiya har guruh uchun alohida chaqirilgani
    sababli, `apply_global=False` berib faqat BITTA guruh uchun qo'llash kerak
    (aks holda bitta global chegirma har guruhda alohida ayirilib, talaba
    guruhlar soniga qarab bir necha barobar ko'p chegirma olib qo'yadi).

    `active_group_ids` berilsa: chegirma bog'langan guruh (d.group_id) talabaning
    hozirgi faol guruhlari orasida bo'lmasa (masalan, talaba boshqa guruhga
    o'tkazilgan, chegirma esa eski guruhga bog'liq qolib ketgan), bu chegirma
    "eskirgan" hisoblanib, xuddi global (group_id=NULL) chegirmadek qo'llanadi —
    aks holda talaba guruh almashtirganda chegirmasi butunlay yo'qolib qolardi.
    """
    if price <= 0 or not discounts:
        return price
    off = ZERO
    for d in discounts:
        stale = bool(d.group_id) and active_group_ids is not None and d.group_id not in active_group_ids
        if d.group_id and not stale:
            if d.group_id != group_id:
                continue
        elif not apply_global:
            continue
        if d.kind == "free_month":
            if month is not None and year is not None and d.month == month and d.year == year:
                return ZERO
        elif d.kind == "monthly":
            off += Decimal(str(d.amount or 0))
        elif d.kind == "one_time":
            if month is not None and year is not None and d.month == month and d.year == year:
                off += Decimal(str(d.amount or 0))
    return max(ZERO, price - off)


def _lesson_dates_in_month(db: Session, group_id: int, student_id: int, month: int, year: int) -> list:
    """Shu guruh/talaba uchun berilgan oyda Attendance'da qayd etilgan dars sanalari."""
    rows = (
        db.query(models.Attendance.lesson_date)
        .filter(
            models.Attendance.group_id == group_id,
            models.Attendance.student_id == student_id,
            extract("month", models.Attendance.lesson_date) == month,
            extract("year", models.Attendance.lesson_date) == year,
        )
        .distinct()
        .all()
    )
    return [r[0] for r in rows]


_PARITY_SCHEDULES = {"toq kunlar": 1, "juft kunlar": 0}  # 1=toq (odd), 0=juft (even) kun


def _scheduled_lesson_dates_in_month(group: models.Group, month: int, year: int) -> Optional[list]:
    """Guruh jadvali "Toq kunlar"/"Juft kunlar" bo'lsa, shu oydagi barcha mos
    sanalarni qaytaradi (yo'qlama hali kiritilmagan bo'lsa ham ishlashi uchun).
    Boshqa jadval formatlari uchun None — chaqiruvchi Attendance'ga qaytadi."""
    sched = (group.schedule or "").strip().lower()
    parity = _PARITY_SCHEDULES.get(sched)
    if parity is None:
        return None
    _, days_in_month = calendar.monthrange(year, month)
    return [date(year, month, d) for d in range(1, days_in_month + 1) if d % 2 == parity]


def apply_vacations_to_price(db: Session, student_id: int, group: models.Group,
                             month: int, year: int, price: Decimal, vacations: list) -> Decimal:
    """Ta'til kunlariga to'g'ri kelgan darslarni oylik narxdan chiqarib tashlaydi.

    `vacations` — talabaning oldindan olingan StudentVacation ro'yxati (chaqiruvchi
    tomonidan bitta so'rov bilan olinishi mumkin, ko'p talaba/guruh holatida N+1
    so'rovlardan qochish uchun). Faqat vacations bo'sh bo'lmasa ishlaydi — aks holda
    narx o'zgarishsiz qaytadi (attendance-independent standart xatti-harakat saqlanadi).

    Formula: kurs_narxi/12 * (jami darslar - ta'tilga tushgan darslar). Yo'qlama
    qilingan (kelgan yoki kelmagan) kunlar hisobga kiradi, faqat ta'til kuni chiqib
    ketadi. Dars sanalari, imkon bo'lsa, guruh jadvalidan ("Toq/Juft kunlar")
    hisoblanadi — shunda hali yo'qlama kiritilmagan bo'lsa ham to'g'ri ishlaydi.
    Boshqa formatdagi jadvallar uchun Attendance'da qayd etilgan sanalarga qaytiladi
    (bu holatda alohida so'rov kerak bo'ladi).
    """
    if price <= 0 or month is None or year is None or not vacations or not group:
        return price
    lesson_dates = _scheduled_lesson_dates_in_month(group, month, year)
    if lesson_dates is None:
        lesson_dates = _lesson_dates_in_month(db, group.id, student_id, month, year)
    if not lesson_dates:
        return price
    vacation_lessons = sum(
        1 for d in lesson_dates if any(v.start_date <= d <= v.end_date for v in vacations)
    )
    if vacation_lessons <= 0:
        return price
    total_lessons = len(lesson_dates)
    billable = max(total_lessons - vacation_lessons, 0)
    per_lesson = price / Decimal(total_lessons)
    return (per_lesson * billable).quantize(Decimal("1"))


def vacation_adjusted_price(db: Session, student_id: int, group_id: int,
                            month: int, year: int, price: Decimal) -> Decimal:
    """`apply_vacations_to_price`ning qulay o'rami — vacations/group'ni o'zi so'raydi.
    Bitta talaba/guruh uchun hisoblashda ishlatiladi (masalan to'lov tafsiloti
    sahifasi). Ko'p talaba uchun ro'yxatda `apply_vacations_to_price`ni to'g'ridan-to'g'ri,
    oldindan olingan vacations bilan chaqiring — N+1 so'rovlardan qochish uchun."""
    if price <= 0 or month is None or year is None:
        return price
    vacations = (
        db.query(models.StudentVacation)
        .filter(models.StudentVacation.student_id == student_id)
        .all()
    )
    if not vacations:
        return price
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    return apply_vacations_to_price(db, student_id, group, month, year, price, vacations)


def _active_group_ids(db: Session, student_id: int) -> set:
    """Talaba hozir a'zo bo'lgan barcha FAOL guruhlar ID'lari to'plami."""
    rows = (
        db.query(models.GroupStudent.group_id)
        .join(models.Group, models.Group.id == models.GroupStudent.group_id)
        .filter(models.GroupStudent.student_id == student_id, models.Group.is_active == True,
                models.GroupStudent.left_at.is_(None))
        .all()
    )
    return {r[0] for r in rows}


def group_completed_lessons(db: Session, group_ids, upto: Optional[date] = None) -> dict:
    """Har guruh uchun kurs progressidagi "o'tilgan darslar" soni: {group_id: son}.

    Faqat guruhning HOZIRGI a'zolaridan kamida bittasi qayd etilgan dars sanalari
    sanaladi. Guruhdan chiqib ketgan/o'tkazilgan talabalarning shu guruhdagi
    davomati (masalan, guruh yangi tarkib bilan qaytadan boshlanganda eski
    talabaning darslari) progressga qo'shilmaydi.

    `upto` berilsa — shu sanagacha, o'sha paytdagi a'zolar bo'yicha (keyinroq
    chiqib ketganlar hali a'zo hisoblanadi). Oylik "o'tilgan darslar" (maosh)
    bu yerdan hisoblanmaydi — u o'qituvchi haqiqatan o'tgan barcha darslarni sanaydi."""
    ids = list(group_ids)
    if not ids:
        return {}
    gs = models.GroupStudent
    q = (
        db.query(models.Attendance.group_id,
                 func.count(func.distinct(models.Attendance.lesson_date)))
        .join(gs, (gs.group_id == models.Attendance.group_id)
                  & (gs.student_id == models.Attendance.student_id))
        .filter(models.Attendance.group_id.in_(ids),
                models.Attendance.is_present.isnot(None))
    )
    if upto is None:
        q = q.filter(gs.left_at.is_(None))
    else:
        q = q.filter(models.Attendance.lesson_date <= upto,
                     gs.left_at.is_(None) | (func.date(gs.left_at) > upto))
    return {gid: cnt for gid, cnt in q.group_by(models.Attendance.group_id).all()}


def covers_month(m, month: int, year: int) -> bool:
    """`m` (GroupStudent) a'zoligi berilgan (month, year)ni o'z ichiga oladimi —
    talaba shu paytda allaqachon qo'shilgan va hali chiqib ketmagan bo'lishi kerak."""
    if m.joined_at and (m.joined_at.year, m.joined_at.month) > (year, month):
        return False
    if m.left_at and (m.left_at.year, m.left_at.month) < (year, month):
        return False
    return True


def group_billable_in(g: models.Group, month: int, year: int) -> bool:
    """Guruh berilgan (month, year) uchun to'lov talab qiladimi. Faol guruh — ha;
    arxivlangan guruh — faqat arxivlangan (`closed_at`) oyigacha, shunda uning o'tgan
    oylari qarz hisobidan unutilmaydi. `closed_at` noma'lum bo'lsa — yo'q."""
    if g.is_active:
        return True
    closed = g.closed_at
    return closed is not None and (year, month) <= (closed.year, closed.month)


def bills_month(m, month: int, year: int) -> bool:
    """`covers_month`ning TO'LOV uchun varianti: talaba shu oyda guruhdan chiqib,
    o'sha oyning o'zida boshqa guruhga (yoki shu guruhga qaytadan) qo'shilgan bo'lsa
    (oy o'rtasida o'tkazish), shu oy faqat YANGI a'zolik bo'yicha hisoblanadi — bir
    oy ikki marta to'lanmasligi uchun. Shunchaki chiqib ketgan talaba (yangi a'zoligi
    yo'q) chiqqan oyi uchun avvalgidek to'laydi. Davomat/maosh `covers_month`ni
    ishlatadi — talaba eski guruhda haqiqatan dars qatnashgan."""
    if not covers_month(m, month, year):
        return False
    if not m.left_at or (m.left_at.year, m.left_at.month) != (year, month):
        return True
    student = m.student
    if student is None:
        return True
    return not any(
        o.id != m.id and o.joined_at and (o.joined_at.year, o.joined_at.month) == (year, month)
        for o in student.group_memberships
    )


def members_covering_month(members: list, month: int, year: int) -> list:
    """Guruh a'zolaridan berilgan (month,year)da haqiqatan a'zo bo'lganlarini
    qaytaradi. Talaba shu guruhga bir necha marta kirib-chiqqan bo'lishi mumkin
    (har biri alohida GroupStudent qatori, ko'ring: `left_at`) — masalan o'tgan
    oyning moliya hisoboti/davomat ro'yxati hozirgi emas, O'SHA PAYTDAGI a'zolar
    ro'yxatini ko'rsatishi kerak."""
    return [m for m in members if covers_month(m, month, year)]


def covers_date(m, d: date) -> bool:
    """`m` (GroupStudent) a'zoligi aniq bitta kunni (`d`) o'z ichiga oladimi —
    `covers_month`ning kun aniqligidagi varianti (davomat belgilash uchun,
    oy darajasidagi aniqlik yetarli bo'lmaydi: oyning bir qismida a'zo bo'lgan,
    keyin chiqib ketgan talaba o'sha oyning HAMMA kunlarida emas)."""
    if m.joined_at and m.joined_at.date() > d:
        return False
    if m.left_at and m.left_at.date() < d:
        return False
    return True


def members_covering_date(members: list, d: date) -> list:
    """`members_covering_month`ning kun aniqligidagi varianti."""
    return [m for m in members if covers_date(m, d)]


def _member_covering(members: list, student_id: int, month: Optional[int], year: Optional[int]):
    """Bitta talabaning berilgan (month, year)ni o'z ichiga olgan a'zolik davrini
    (stint) topadi. month/year berilmasa — hozir FAOL bo'lgan a'zolikni
    (left_at yo'q) qaytaradi."""
    candidates = [m for m in members if m.student_id == student_id]
    if not candidates:
        return None
    if month is None or year is None:
        return next((m for m in candidates if m.left_at is None), None)
    return next((m for m in candidates if bills_month(m, month, year)), None)


def _primary_group_id(db: Session, student_id: int) -> Optional[int]:
    """Talabaning global (group_id=NULL) yoki eskirgan (guruhi endi mos
    kelmaydigan) chegirmasi faqat BITTA guruhga qo'llanishi uchun — eng
    kichik ID'li faol guruh 'asosiy' hisoblanadi."""
    ids = _active_group_ids(db, student_id)
    return min(ids) if ids else None


def student_month_owed(db: Session, student_id: int, group_id: int,
                       month: int = None, year: int = None, *,
                       group: Optional[models.Group] = None,
                       discounts: Optional[list] = None,
                       vacations: Optional[list] = None,
                       active_group_ids: Optional[set] = None) -> Decimal:
    """Bitta guruh uchun oylik to'liq summa: tarif narxi, aks holda guruh narxi.

    Ta'til (agar bor bo'lsa) va special chegirmalar shu yerda qo'llanadi (yagona
    manba). month/year berilsa free_month chegirmasi va ta'til hisobga olinadi.

    `group`/`discounts`/`vacations`/`active_group_ids` oldindan olingan bo'lsa
    (masalan `student_cumulative_owed` ko'p oy uchun bitta talabani hisoblayotganda),
    shu qiymatlar ishlatiladi va mos DB so'rovlari o'tkazib yuboriladi — bu qiymatlar
    month/year'ga bog'liq emas, shuning uchun bir marta olib, har oyda qayta
    ishlatish xavfsiz. Berilmasa, avvalgidek funksiya o'zi so'raydi.
    """
    g = group if group is not None else db.query(models.Group).filter(models.Group.id == group_id).first()
    if not g:
        return ZERO
    if g.start_date:
        if month is not None and year is not None:
            if (g.start_date.year, g.start_date.month) > (year, month):
                return ZERO  # guruh so'ralgan oyda hali boshlanmagan edi
        elif g.start_date.date() > tz.today():
            return ZERO  # guruh hali boshlanmagan — talaba hali qarzdor emas
    member = _member_covering(g.members, student_id, month, year)
    if month is None and member and member.joined_at and member.joined_at.date() > tz.today():
        return ZERO  # talaba hali shu guruhga qo'shilmagan — qarzdor emas
    if member is None:
        return ZERO  # talaba so'ralgan (oy,yil)da shu guruh a'zosi bo'lmagan
                     # (hali qo'shilmagan, yoki shu paytgacha allaqachon chiqib ketgan)
    if member.tariff:
        price = Decimal(str(member.tariff.price))
    elif g.course_price and Decimal(str(g.course_price)) > 0:
        price = Decimal(str(g.course_price))
    else:
        price = ZERO
    if price <= 0:
        return ZERO
    if vacations is None:
        price = vacation_adjusted_price(db, student_id, group_id, month, year, price)
    else:
        price = apply_vacations_to_price(db, student_id, g, month, year, price, vacations)
    if active_group_ids is None:
        active_group_ids = _active_group_ids(db, student_id)
    primary_group_id = min(active_group_ids) if active_group_ids else None
    apply_global = primary_group_id is None or primary_group_id == group_id
    if discounts is None:
        discounts = active_special_discounts(db, student_id)
    price = apply_special_discounts(price, discounts, group_id, month, year, apply_global=apply_global,
                                    active_group_ids=active_group_ids)
    return price.quantize(Decimal("1")) if price > 0 else ZERO


def student_month_paid(db: Session, student_id: int, group_id: int, month: int, year: int) -> Decimal:
    """Talabaning shu guruh + oy uchun jami to'lovi."""
    total = (
        db.query(func.sum(models.Payment.amount))
        .filter(
            models.Payment.group_id == group_id,
            models.Payment.student_id == student_id,
            models.Payment.month == month,
            models.Payment.year == year,
        )
        .scalar()
    )
    return total or ZERO


def student_cumulative_owed(db: Session, student: models.Student, upto_year: int = None, upto_month: int = None,
                            *, discounts: Optional[list] = None, vacations: Optional[list] = None) -> Decimal:
    """Talaba ro'yxatdan o'tgandan (yoki guruhga qo'shilgandan) bugungi oygacha
    guruhlari bo'yicha jami qarzi — jamlangan (kumulyativ) hisob-kitob uchun.
    Arxivlangan guruh arxivlangan oyigacha hisoblanadi (`group_billable_in`).
    Har bir o'tgan oy alohida `student_month_owed` orqali hisoblanadi (tarif,
    chegirma va ta'til hisobga olingan holda), so'ng barchasi qo'shiladi.

    `discounts`/`vacations` — chaqiruvchi tomonidan ko'p talaba uchun bitta bulk
    so'rov bilan oldindan olingan bo'lishi mumkin (masalan to'lovlar/qarzdorlar
    ro'yxati). Berilmasa, shu yerda bir marta (butun oy sikli uchun, har oyda
    emas) so'raladi — bu ikkalasi ham month/year'ga bog'liq emas, shuning uchun
    oldin har oy qaytadan so'ralishi sof ortiqcha DB yuklama edi."""
    today = tz.today()
    if upto_year is None or upto_month is None:
        upto_year, upto_month = today.year, today.month
    if discounts is None:
        discounts = active_special_discounts(db, student.id)
    if vacations is None:
        vacations = (
            db.query(models.StudentVacation)
            .filter(models.StudentVacation.student_id == student.id)
            .all()
        )
    active_group_ids = _active_group_ids(db, student.id)
    total = ZERO
    billed_groups = set()   # a'zolik bo'yicha qarzi hisoblanadigan guruhlar
    billed_months = set()   # a'zolik bo'yicha hisoblangan (yil, oy)lar
    for m in student.group_memberships:
        g = m.group
        if not g:
            continue
        if not g.is_active and g.closed_at is None:
            continue
        start = None
        if g.start_date:
            start = (g.start_date.year, g.start_date.month)
        if m.joined_at:
            joined = (m.joined_at.year, m.joined_at.month)
            start = joined if start is None else max(start, joined)
        if start is None:
            continue
        # Talaba shu a'zolik davrida (stint) qachongacha qarzdor bo'lgan — agar
        # keyinroq shu guruhdan chiqarilgan bo'lsa (`left_at`), o'sha oydan
        # keyingi oylar bu stint uchun hisoblanmaydi (boshqa stint yoki boshqa
        # guruh bo'lsa, ular student.group_memberships'da alohida qator sifatida
        # o'z chegarasi bilan hisoblanadi).
        end = (upto_year, upto_month)
        if m.left_at:
            end = min(end, (m.left_at.year, m.left_at.month))
        if not g.is_active:
            # Arxivlangan guruh — arxivlangan oygacha hisoblanadi (o'tgan oylar unutilmaydi)
            end = min(end, (g.closed_at.year, g.closed_at.month))
        billed_groups.add(g.id)
        if start > end:
            continue
        y, mo = start
        while (y, mo) <= end:
            if bills_month(m, mo, y):   # oy o'rtasida o'tkazilgan oy — faqat yangi a'zolikda
                total += student_month_owed(db, student.id, g.id, mo, y,
                                            group=g, discounts=discounts, vacations=vacations,
                                            active_group_ids=active_group_ids)
            billed_months.add((y, mo))
            mo += 1
            if mo > 12:
                mo = 1
                y += 1
    # A'zoligi saqlanmagan guruh (eski versiyada a'zolik o'chirib yuborilgan, yoki
    # arxiv sanasi noma'lum) bo'yicha to'lov — o'sha oyning o'zini yopadi. Aks holda
    # u "ortiqcha to'lov" bo'lib boshqa oy qarzini yopib yuboradi (masalan S007 dagi
    # avgust to'lovi S003 dagi sentyabr qarzini). Istisnolar — to'lov avans bo'lib
    # qoladi: a'zoligi bor guruhning boshqa oyi (masalan guruh boshlanishidan oldin),
    # yoki shu oy boshqa guruh a'zoligi bo'yicha hisoblangan (oy o'rtasida o'tkazilgan
    # talaba — eski guruhga to'lagan oyi yangi guruhdagi o'sha oyni yopadi).
    rows = (
        db.query(models.Payment.group_id, models.Payment.year, models.Payment.month,
                 func.sum(models.Payment.amount))
        .filter(models.Payment.student_id == student.id)
        .group_by(models.Payment.group_id, models.Payment.year, models.Payment.month)
        .all()
    )
    for gid, y, mo, amount in rows:
        if (gid not in billed_groups and (y, mo) not in billed_months
                and (y, mo) <= (upto_year, upto_month)):
            total += Decimal(str(amount or 0))
    return total


def student_total_paid_all_time(db: Session, student_id: int) -> Decimal:
    """Talabaning butun tarix davomida jami to'lovi (oy/yilga bog'liq emas)."""
    total = db.query(func.sum(models.Payment.amount)).filter(models.Payment.student_id == student_id).scalar()
    return Decimal(str(total or 0))


def student_cumulative_balance(db: Session, student: models.Student, upto_year: int = None, upto_month: int = None) -> Decimal:
    """Talabaning JAMLANGAN moliyaviy holati: musbat = ortiqcha to'lov (balans),
    manfiy = qarz. Oy-oy emas — bitta oyda ortiqcha to'langan summa boshqa
    oydagi qarzni avtomatik yopadi (yagona manba, CRM va ota-ona ilovasi
    bir xil natija ko'rishi uchun)."""
    owed = student_cumulative_owed(db, student, upto_year, upto_month)
    paid = student_total_paid_all_time(db, student.id) + Decimal(str(student.advance_balance or 0))
    return paid - owed


def advance_eligible_month(student: models.Student) -> Optional[tuple]:
    """Avans balansi (`Student.advance_balance`) qaysi (yil, oy) uchun
    qo'llanishi kerak — talabaning eng erta boshlangan faol guruhi bo'yicha
    (yoki guruh bo'lmasa/start_date yo'q bo'lsa, ro'yxatga olingan oyi).

    Muhim: bu FAQAT bitta oyga tegishli bo'lishi kerak — aks holda avans har
    so'ralgan oyda qayta-qayta qo'llanib, cheksiz bepul oylarga aylanib
    ketadi (avans hech qachon "sarflanmagan" hisoblanadi, chunki hech qayerda
    kamaytirilmaydi)."""
    starts = [
        m.group.start_date for m in student.group_memberships
        if m.group and m.group.is_active and m.group.start_date
    ]
    base = min(starts) if starts else student.created_at
    if not base:
        return None
    return (base.year, base.month)


def advance_amount_for_month(student: models.Student, month: int, year: int) -> Decimal:
    """`student.advance_balance`ni faqat talabaning birinchi oyi uchun qaytaradi
    — boshqa har qanday oy uchun ZERO (avans cheksiz qayta berilib ketmasligi
    uchun, ko'ring: `advance_eligible_month`)."""
    balance = Decimal(str(student.advance_balance or 0))
    if balance <= 0:
        return ZERO
    if advance_eligible_month(student) != (year, month):
        return ZERO
    return balance


def payment_status(total_owed: Decimal, total_paid: Decimal, advance: Decimal = ZERO) -> str:
    """Holat: none (to'lov talab qilinmaydi) | paid | partial | debtor."""
    covered = total_paid + advance
    if total_owed <= 0:
        return "none"
    if covered >= total_owed:
        return "paid"
    if covered > 0:
        return "partial"
    return "debtor"
