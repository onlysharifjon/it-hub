import asyncio
import logging
from datetime import date, datetime, time, timedelta

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

import crm_client
from database import async_session
from keyboards import (
    BTN_ATTENDANCE,
    BTN_LINK_PARENT,
    BTN_PAYMENT,
    admin_menu_keyboard,
    attendance_mode_keyboard,
    attendance_select_keyboard,
    crm_groups_keyboard,
    crm_students_keyboard,
    employees_keyboard,
    payment_report_choice_keyboard,
)
from handlers.profile import _student_detail_text
from models import Attendance, Employee, ParentLink
from states import AttendanceFlow, BotSettings, LinkParent, PaymentFlow
from utils import (
    apply_bot_commands,
    get_employee,
    get_setting,
    list_workers,
    reply_keyboard_for_employee,
    safe_edit_text,
    set_setting,
)

router = Router(name="crm")

logger = logging.getLogger(__name__)


async def _require_admin(session, telegram_id: int) -> Employee | None:
    employee = await get_employee(session, telegram_id)
    return employee if employee and employee.is_admin else None


async def _show_crm_error(callback: CallbackQuery, error: Exception) -> None:
    await callback.answer(f"CRM xatosi: {error}", show_alert=True)


async def _reply_crm_error(message: Message, error: Exception) -> None:
    await message.answer(f"CRM xatosi: {error}")


def _tashkent_now() -> datetime:
    return datetime.utcnow() + timedelta(hours=5)


def _tashkent_today_bounds_utc() -> tuple[datetime, datetime]:
    tashkent_date = _tashkent_now().date()
    start_utc = datetime.combine(tashkent_date, time.min) - timedelta(hours=5)
    return start_utc, start_utc + timedelta(days=1)


def _format_duration(total: timedelta) -> str | None:
    seconds = int(total.total_seconds())
    if seconds <= 0:
        return None
    hours, minutes = divmod(seconds // 60, 60)
    if hours and minutes:
        return f"{hours} soat {minutes} daqiqa"
    if hours:
        return f"{hours} soat"
    return f"{minutes} daqiqa"


async def _today_status(session, crm_student_ids: list[int]) -> dict[int, str]:
    if not crm_student_ids:
        return {}
    start, end = _tashkent_today_bounds_utc()
    result = await session.execute(
        select(Attendance)
        .where(Attendance.crm_student_id.in_(crm_student_ids))
        .where(Attendance.created_at >= start, Attendance.created_at < end)
        .order_by(Attendance.created_at)
    )
    status: dict[int, str] = {}
    for row in result.scalars().all():
        status[row.crm_student_id] = row.kind
    return status


async def _today_duration(session, crm_student_id: int) -> str | None:
    start, end = _tashkent_today_bounds_utc()
    result = await session.execute(
        select(Attendance)
        .where(Attendance.crm_student_id == crm_student_id)
        .where(Attendance.created_at >= start, Attendance.created_at < end)
        .order_by(Attendance.created_at)
    )
    total = timedelta()
    arrived_at: datetime | None = None
    for row in result.scalars().all():
        if row.kind == "arrived":
            arrived_at = row.created_at
        elif row.kind == "left" and arrived_at is not None:
            total += row.created_at - arrived_at
            arrived_at = None
    return _format_duration(total)


async def _notify_targets(session, crm_student_id: int) -> list[int]:
    """Telegram chat ids to notify for this student: linked parents if any, else the
    single default fallback chat id."""
    result = await session.execute(
        select(ParentLink).where(ParentLink.crm_student_id == crm_student_id)
    )
    links = result.scalars().all()
    if links:
        ids = []
        for link in links:
            employee = await session.get(Employee, link.employee_id)
            if employee:
                ids.append(employee.telegram_id)
        if ids:
            return ids
    default_chat_id = await get_setting(session, "default_parent_chat_id")
    return [int(default_chat_id)] if default_chat_id else []


# ── Ota-onani biriktirish (botning o'z bazasida, CRMga yozmaydi) ────────────────


@router.message(F.text.in_({"/otaona", BTN_LINK_PARENT}))
async def crm_link_start(message: Message, state: FSMContext) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, message.from_user.id)
        if not admin:
            return
        employees = await list_workers(session)
    if not employees:
        await message.answer("Hozircha botga start bergan xodimlar yo'q.")
        return
    await state.set_state(LinkParent.choosing_employee)
    await message.answer(
        "Qaysi foydalanuvchini ota-ona sifatida biriktirmoqchisiz?",
        reply_markup=employees_keyboard(employees, "link_emp", back_callback="adm_menu"),
    )


@router.callback_query(LinkParent.choosing_employee, F.data.startswith("link_emp:"))
async def crm_link_choose_employee(callback: CallbackQuery, state: FSMContext) -> None:
    employee_id = int(callback.data.split(":")[1])
    await state.update_data(link_employee_id=employee_id)
    try:
        groups = await crm_client.get_groups()
    except crm_client.CRMError as error:
        await _show_crm_error(callback, error)
        return
    if not groups:
        await callback.answer("CRMda faol guruh topilmadi.", show_alert=True)
        return
    await state.set_state(LinkParent.choosing_group)
    await safe_edit_text(
        callback.message,
        "O'quvchi qaysi guruhda?",
        reply_markup=crm_groups_keyboard(groups, "link_group", back_callback="adm_menu"),
    )
    await callback.answer()


@router.callback_query(LinkParent.choosing_group, F.data.startswith("link_group:"))
async def crm_link_choose_group(callback: CallbackQuery, state: FSMContext) -> None:
    group_id = int(callback.data.split(":")[1])
    try:
        detail = await crm_client.get_group_detail(group_id)
    except crm_client.CRMError as error:
        await _show_crm_error(callback, error)
        return
    members = detail.get("members", [])
    if not members:
        await callback.answer("Bu guruhda o'quvchi yo'q.", show_alert=True)
        return
    await state.update_data(
        link_group_id=group_id, link_group_name=detail.get("name", ""), link_members=members
    )
    await state.set_state(LinkParent.choosing_student)
    await safe_edit_text(
        callback.message,
        "Qaysi o'quvchining ota-onasi bu foydalanuvchi?",
        reply_markup=crm_students_keyboard(members, "link_student", back_callback="adm_menu"),
    )
    await callback.answer()


@router.callback_query(LinkParent.choosing_student, F.data.startswith("link_student:"))
async def crm_link_choose_student(callback: CallbackQuery, state: FSMContext) -> None:
    student_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    members = {m["student_id"]: m["student_name"] for m in data.get("link_members", [])}
    student_name = members.get(student_id, str(student_id))
    async with async_session() as session:
        employee = await session.get(Employee, data["link_employee_id"])
        if employee is None:
            await state.clear()
            await callback.answer("Xodim topilmadi.", show_alert=True)
            return
        result = await session.execute(
            select(ParentLink).where(
                ParentLink.employee_id == employee.id, ParentLink.crm_student_id == student_id
            )
        )
        if result.scalar_one_or_none() is None:
            session.add(
                ParentLink(
                    employee_id=employee.id,
                    crm_student_id=student_id,
                    student_name=student_name,
                    crm_group_id=data.get("link_group_id", 0),
                    group_name=data.get("link_group_name", ""),
                )
            )
            await session.commit()
        employee_name = employee.full_name
        employee_telegram_id = employee.telegram_id
        await apply_bot_commands(callback.bot, session, employee)
        try:
            keyboard = await reply_keyboard_for_employee(session, employee)
            await callback.bot.send_message(
                employee_telegram_id,
                f"Siz {student_name}ning ota-onasi sifatida biriktirildingiz. Pastdagi tugmalar orqali davom eting.",
                reply_markup=keyboard,
            )
        except Exception:
            pass
    await state.clear()
    await safe_edit_text(
        callback.message,
        f"✅ {employee_name} — {student_name}ning ota-onasi sifatida biriktirildi.",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()


# ── Davomat: kelish/ketish (botning o'z bazasida) ───────────────────────────────


@router.message(F.text.in_({"/davomat", BTN_ATTENDANCE}))
async def crm_attendance_start(message: Message, state: FSMContext) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, message.from_user.id)
        if not admin:
            return
    try:
        groups = await crm_client.get_groups()
    except crm_client.CRMError as error:
        await _reply_crm_error(message, error)
        return
    if not groups:
        await message.answer("CRMda faol guruh topilmadi.")
        return
    await state.set_state(AttendanceFlow.choosing_group)
    await message.answer(
        "Davomat uchun guruhni tanlang:",
        reply_markup=crm_groups_keyboard(groups, "att_group", back_callback="adm_menu"),
    )


@router.callback_query(AttendanceFlow.choosing_group, F.data.startswith("att_group:"))
async def crm_attendance_choose_group(callback: CallbackQuery, state: FSMContext) -> None:
    group_id = int(callback.data.split(":")[1])
    try:
        detail = await crm_client.get_group_detail(group_id)
    except crm_client.CRMError as error:
        await _show_crm_error(callback, error)
        return
    members = detail.get("members", [])
    if not members:
        await callback.answer("Bu guruhda o'quvchi yo'q.", show_alert=True)
        return
    await state.update_data(att_group_id=group_id, att_group_name=detail.get("name", ""), att_members=members)
    await state.set_state(AttendanceFlow.choosing_mode)
    await safe_edit_text(
        callback.message,
        f"{detail.get('name', '')} — nima qilmoqchisiz?",
        reply_markup=attendance_mode_keyboard("adm_menu"),
    )
    await callback.answer()


@router.callback_query(AttendanceFlow.choosing_mode, F.data == "att_mode_arrived")
async def crm_attendance_mode_arrived(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.update_data(att_selected=[])
    await state.set_state(AttendanceFlow.marking_arrived)
    await safe_edit_text(
        callback.message,
        "Darsga kelganlarni belgilang:",
        reply_markup=attendance_select_keyboard(
            data["att_members"], set(), "att_arr", "att_confirm_arrived", "adm_menu"
        ),
    )
    await callback.answer()


@router.callback_query(AttendanceFlow.choosing_mode, F.data == "att_mode_view")
async def crm_attendance_mode_view(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(AttendanceFlow.choosing_view_student)
    await safe_edit_text(
        callback.message,
        "Qaysi o'quvchining davomat tarixini ko'rmoqchisiz?",
        reply_markup=crm_students_keyboard(data["att_members"], "att_view_student", back_callback="adm_menu"),
    )
    await callback.answer()


@router.callback_query(AttendanceFlow.choosing_view_student, F.data.startswith("att_view_student:"))
async def crm_attendance_view_student(callback: CallbackQuery, state: FSMContext) -> None:
    student_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    members = {m["student_id"]: m["student_name"] for m in data["att_members"]}
    student_name = members.get(student_id, str(student_id))
    async with async_session() as session:
        text = await _student_detail_text(
            session, student_id, student_name, data["att_group_id"], data["att_group_name"]
        )
    await state.clear()
    await safe_edit_text(callback.message, text, reply_markup=admin_menu_keyboard())
    await callback.answer()


@router.callback_query(AttendanceFlow.choosing_mode, F.data == "att_mode_left")
async def crm_attendance_mode_left(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    members = data["att_members"]
    async with async_session() as session:
        status = await _today_status(session, [m["student_id"] for m in members])
    eligible = [m for m in members if status.get(m["student_id"]) == "arrived"]
    if not eligible:
        await callback.answer("Hozircha hech kim 'keldi' deb belgilanmagan.", show_alert=True)
        return
    await state.update_data(att_selected=[], att_left_members=eligible)
    await state.set_state(AttendanceFlow.marking_left)
    await safe_edit_text(
        callback.message,
        "Ketganlarni belgilang (faqat kelganlar ko'rsatiladi):",
        reply_markup=attendance_select_keyboard(eligible, set(), "att_left", "att_confirm_left", "adm_menu"),
    )
    await callback.answer()


@router.callback_query(AttendanceFlow.marking_arrived, F.data.startswith("att_arr:"))
async def crm_attendance_toggle_arrived(callback: CallbackQuery, state: FSMContext) -> None:
    student_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected = set(data.get("att_selected", []))
    selected.symmetric_difference_update({student_id})
    await state.update_data(att_selected=list(selected))
    await safe_edit_text(
        callback.message,
        "Darsga kelganlarni belgilang:",
        reply_markup=attendance_select_keyboard(
            data["att_members"], selected, "att_arr", "att_confirm_arrived", "adm_menu"
        ),
    )
    await callback.answer()


@router.callback_query(AttendanceFlow.marking_arrived, F.data == "att_confirm_arrived")
async def crm_attendance_confirm_arrived(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    selected = set(data.get("att_selected", []))
    if not selected:
        await callback.answer("Hech kim belgilanmadi.", show_alert=True)
        return
    members = {m["student_id"]: m["student_name"] for m in data["att_members"]}
    time_str = _tashkent_now().strftime("%H:%M")
    async with async_session() as session:
        marker = await get_employee(session, callback.from_user.id)
        for student_id in selected:
            session.add(
                Attendance(
                    crm_student_id=student_id,
                    student_name=members[student_id],
                    crm_group_id=data["att_group_id"],
                    group_name=data["att_group_name"],
                    kind="arrived",
                    marked_by_id=marker.id,
                )
            )
        await session.commit()
        targets = {student_id: await _notify_targets(session, student_id) for student_id in selected}
    for student_id in selected:
        for chat_id in targets.get(student_id, []):
            try:
                await callback.bot.send_message(
                    chat_id, f"✅ Farzandingiz {members[student_id]} darsga keldi\n🕐 {time_str}"
                )
            except Exception:
                pass
    await state.clear()
    await safe_edit_text(
        callback.message,
        f"✅ {len(selected)} ta o'quvchi keldi deb belgilandi.",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(AttendanceFlow.marking_left, F.data.startswith("att_left:"))
async def crm_attendance_toggle_left(callback: CallbackQuery, state: FSMContext) -> None:
    student_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected = set(data.get("att_selected", []))
    selected.symmetric_difference_update({student_id})
    await state.update_data(att_selected=list(selected))
    await safe_edit_text(
        callback.message,
        "Ketganlarni belgilang (faqat kelganlar ko'rsatiladi):",
        reply_markup=attendance_select_keyboard(
            data["att_left_members"], selected, "att_left", "att_confirm_left", "adm_menu"
        ),
    )
    await callback.answer()


@router.callback_query(AttendanceFlow.marking_left, F.data == "att_confirm_left")
async def crm_attendance_confirm_left(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    selected = set(data.get("att_selected", []))
    if not selected:
        await callback.answer("Hech kim belgilanmadi.", show_alert=True)
        return
    members = {m["student_id"]: m["student_name"] for m in data["att_left_members"]}
    time_str = _tashkent_now().strftime("%H:%M")
    async with async_session() as session:
        marker = await get_employee(session, callback.from_user.id)
        for student_id in selected:
            session.add(
                Attendance(
                    crm_student_id=student_id,
                    student_name=members[student_id],
                    crm_group_id=data["att_group_id"],
                    group_name=data["att_group_name"],
                    kind="left",
                    marked_by_id=marker.id,
                )
            )
        await session.commit()
        durations = {student_id: await _today_duration(session, student_id) for student_id in selected}
        targets = {student_id: await _notify_targets(session, student_id) for student_id in selected}
    for student_id in selected:
        text = f"\U0001f3e0 Farzandingiz {members[student_id]} o'quv markazdan ketdi\n🕐 {time_str}"
        duration = durations.get(student_id)
        if duration:
            text += f"\n\U0001f553 Bugun jami {duration} bo'ldi."
        for chat_id in targets.get(student_id, []):
            try:
                await callback.bot.send_message(chat_id, text)
            except Exception:
                pass
    await state.clear()
    await safe_edit_text(
        callback.message,
        f"✅ {len(selected)} ta o'quvchi ketdi deb belgilandi.",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()


# ── To'lov holati ────────────────────────────────────────────────────────────


def _format_payment_summary(summary: dict) -> str:
    def _money(value) -> str:
        return f"{int(float(value)):,}".replace(",", " ")

    status_labels = {
        "paid": "✅ To'langan",
        "partial": "\U0001f7e1 Qisman to'langan",
        "debtor": "\U0001f534 Qarzdor",
        "none": "— (guruh yo'q)",
    }
    lines = [
        f"\U0001f4b0 {summary['student_name']} — {summary['month']}/{summary['year']}",
        f"Holat: {status_labels.get(summary['payment_status'], summary['payment_status'])}",
        f"Jami kerak: {_money(summary['total_owed'])} so'm",
        f"To'langan: {_money(summary['total_paid'])} so'm",
        f"Qarz: {_money(summary['debt'])} so'm",
    ]
    return "\n".join(lines)


@router.message(F.text.in_({"/tolov", BTN_PAYMENT}))
async def payment_start(message: Message, state: FSMContext) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, message.from_user.id)
        if not admin:
            return
    try:
        groups = await crm_client.get_groups()
    except crm_client.CRMError as error:
        await _reply_crm_error(message, error)
        return
    if not groups:
        await message.answer("CRMda faol guruh topilmadi.")
        return
    await state.set_state(PaymentFlow.choosing_group)
    await message.answer(
        "Qaysi guruhdagi o'quvchi?",
        reply_markup=crm_groups_keyboard(groups, "pay_group", back_callback="adm_menu"),
    )


@router.callback_query(PaymentFlow.choosing_group, F.data.startswith("pay_group:"))
async def payment_choose_group(callback: CallbackQuery, state: FSMContext) -> None:
    group_id = int(callback.data.split(":")[1])
    try:
        detail = await crm_client.get_group_detail(group_id)
    except crm_client.CRMError as error:
        await _show_crm_error(callback, error)
        return
    members = detail.get("members", [])
    if not members:
        await callback.answer("Bu guruhda o'quvchi yo'q.", show_alert=True)
        return
    await state.set_state(PaymentFlow.choosing_student)
    await safe_edit_text(
        callback.message,
        "O'quvchini tanlang:",
        reply_markup=crm_students_keyboard(members, "pay_student", back_callback="adm_menu"),
    )
    await callback.answer()


@router.callback_query(PaymentFlow.choosing_student, F.data.startswith("pay_student:"))
async def payment_choose_student(callback: CallbackQuery, state: FSMContext) -> None:
    student_id = int(callback.data.split(":")[1])
    try:
        summary = await crm_client.get_payment_summary(student_id)
    except crm_client.CRMError as error:
        await _show_crm_error(callback, error)
        return
    await state.clear()
    await safe_edit_text(callback.message, _format_payment_summary(summary), reply_markup=admin_menu_keyboard())
    await callback.answer()


async def _collect_payment_status(groups: list[dict]) -> tuple[list[str], list[str], int, int]:
    """Returns (paid_names, debtor_names, total_students, errors)."""
    students: dict[int, str] = {}
    for group in groups:
        try:
            detail = await crm_client.get_group_detail(group["id"])
        except crm_client.CRMError:
            continue
        for member in detail.get("members", []):
            students[member["student_id"]] = member["student_name"]

    if not students:
        return [], [], 0, 0

    semaphore = asyncio.Semaphore(8)
    paid: list[str] = []
    debtors: list[str] = []
    errors = 0

    async def _check(student_id: int, name: str) -> None:
        nonlocal errors
        async with semaphore:
            try:
                summary = await crm_client.get_payment_summary(student_id)
            except crm_client.CRMError:
                errors += 1
                return
            if summary["payment_status"] == "paid":
                paid.append(name)
            elif float(summary.get("debt") or 0) > 0:
                debtors.append(name)

    await asyncio.gather(*(_check(sid, name) for sid, name in students.items()))
    return paid, debtors, len(students), errors


def _format_payment_list(kind: str, names: list[str], total: int, errors: int) -> str:
    label = "✅ To'lagan" if kind == "paid" else "\U0001f534 Qarzdor"
    lines = [f"\U0001f4ca To'lov hisoboti — {label} o'quvchilar: {len(names)}/{total}", ""]
    if not names:
        lines.append("Hech kim topilmadi.")
    else:
        lines.extend(f"• {name}" for name in names[:60])
        if len(names) > 60:
            lines.append(f"... va yana {len(names) - 60} kishi")
    if errors:
        lines.append(f"\n⚠️ {errors} ta o'quvchi uchun ma'lumot olinmadi.")
    return "\n".join(lines)


@router.message(F.text == "/tolovhisoboti")
async def payment_report(message: Message) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, message.from_user.id)
        if not admin:
            return
    await message.answer(
        "To'lov hisoboti: kimlarni ko'rmoqchisiz?", reply_markup=payment_report_choice_keyboard()
    )


@router.callback_query(F.data == "rpt_payment")
async def payment_report_cb(callback: CallbackQuery) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
    await safe_edit_text(
        callback.message,
        "To'lov hisoboti: kimlarni ko'rmoqchisiz?",
        reply_markup=payment_report_choice_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("payrep:"))
async def payment_report_show(callback: CallbackQuery) -> None:
    kind = callback.data.split(":")[1]
    async with async_session() as session:
        admin = await _require_admin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
    try:
        groups = await crm_client.get_groups()
    except crm_client.CRMError as error:
        await _show_crm_error(callback, error)
        return
    await callback.answer("Hisobot tayyorlanmoqda, biroz kuting...")
    paid, debtors, total, errors = await _collect_payment_status(groups)
    names = paid if kind == "paid" else debtors
    await callback.message.answer(_format_payment_list(kind, names, total, errors))


# ── To'lov eslatmasi (oy boshida avtomatik) ─────────────────────────────────────


async def send_monthly_payment_reminders(bot: Bot) -> None:
    """1- va 3-sanada, hali shu oy to'lovi qilinmagan har bir biriktirilgan
    o'quvchi uchun ota-onaga eslatma yuboradi."""
    async with async_session() as session:
        result = await session.execute(select(ParentLink))
        links = result.scalars().all()
    if not links:
        return
    month_names = [
        "", "yanvar", "fevral", "mart", "aprel", "may", "iyun",
        "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
    ]
    today = _tashkent_now().date()
    month_name = month_names[today.month]
    seen_students: set[int] = set()
    for link in links:
        if link.crm_student_id in seen_students:
            continue
        seen_students.add(link.crm_student_id)
        try:
            summary = await crm_client.get_payment_summary(link.crm_student_id)
        except crm_client.CRMError as error:
            logger.warning("Payment reminder skipped for student %s: %s", link.crm_student_id, error)
            continue
        if summary["payment_status"] == "paid":
            continue
        text = (
            f"\U0001f4c5 Hurmatli ota-ona! {month_name.capitalize()} oyi uchun "
            f"o'quv markaziga to'lov hali amalga oshirilmagan.\n"
            f"Iltimos, {today.month}-oyning 5-sanasigacha to'lovni amalga oshiring.\n"
            f"Qarz: {int(float(summary.get('debt') or 0)):,}".replace(",", " ") + " so'm"
        )
        async with async_session() as session:
            employee = await session.get(Employee, link.employee_id)
        if employee:
            try:
                await bot.send_message(employee.telegram_id, text)
            except Exception:
                pass


async def payment_reminder_loop(bot: Bot) -> None:
    while True:
        now = _tashkent_now()
        if now.day in (1, 3) and now.hour == 9:
            try:
                await send_monthly_payment_reminders(bot)
            except Exception:
                logger.exception("Monthly payment reminder run failed")
            await asyncio.sleep(3600)
        await asyncio.sleep(600)


# ── Sozlamalar ───────────────────────────────────────────────────────────────


@router.message(F.text == "/otaonaid")
async def set_default_parent_start(message: Message, state: FSMContext) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, message.from_user.id)
        if not admin:
            return
        current = await get_setting(session, "default_parent_chat_id")
    await state.set_state(BotSettings.default_parent_id)
    await message.answer(
        f"Hozirgi standart ota-ona Telegram ID: <code>{current}</code>\n\nYangi ID ni kiriting (raqam):"
    )


@router.callback_query(F.data == "set_default_parent")
async def set_default_parent_start_cb(callback: CallbackQuery, state: FSMContext) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        current = await get_setting(session, "default_parent_chat_id")
    await state.set_state(BotSettings.default_parent_id)
    await safe_edit_text(
        callback.message,
        f"Hozirgi standart ota-ona Telegram ID: <code>{current}</code>\n\nYangi ID ni kiriting (raqam):",
    )
    await callback.answer()


@router.message(BotSettings.default_parent_id, F.text)
async def set_default_parent_save(message: Message, state: FSMContext) -> None:
    raw = message.text.strip()
    if not raw.lstrip("-").isdigit():
        await message.answer("Faqat raqam kiriting:")
        return
    async with async_session() as session:
        await set_setting(session, "default_parent_chat_id", raw)
    await state.clear()
    await message.answer(f"✅ Standart ota-ona ID yangilandi: <code>{raw}</code>", reply_markup=admin_menu_keyboard())
