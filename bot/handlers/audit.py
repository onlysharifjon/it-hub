from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select

from database import async_session
from keyboards import (
    BTN_FINE_GIVE,
    BTN_FINE_REPORT,
    BTN_MY_TEMPLATES,
    audit_menu_keyboard,
    audit_templates_manage_keyboard,
    employees_keyboard,
    fine_templates_keyboard,
    fine_totals_keyboard,
    photo_prompt_keyboard,
)
from models import Employee, Fine, FineTemplate
from states import AuditAuth, FineFlow, NewFineTemplate, ReportFlow
from utils import (
    apply_bot_commands,
    get_active_audit_account,
    get_employee,
    get_setting,
    is_privileged,
    list_admins,
    list_employees_with_fines,
    list_staff,
    reply_keyboard_for_employee,
    safe_edit_text,
    verify_password,
    visible_fine_templates,
)

router = Router(name="audit")


@router.message(F.text == "/audit")
async def audit_entry(message: Message, state: FSMContext) -> None:
    async with async_session() as session:
        employee = await get_employee(session, message.from_user.id)
        if employee is None:
            await message.answer("Avval botga /start bosing.")
            return
        if employee.is_admin:
            await message.answer("Audit paneli:", reply_markup=audit_menu_keyboard())
            return
        account = await get_active_audit_account(session, employee.id)
        if account is None:
            await message.answer("Sizga audit huquqi berilmagan.")
            return
    await state.set_state(AuditAuth.login)
    await message.answer("Login kiriting:")


@router.message(AuditAuth.login, F.text)
async def audit_login(message: Message, state: FSMContext) -> None:
    async with async_session() as session:
        employee = await get_employee(session, message.from_user.id)
        account = await get_active_audit_account(session, employee.id) if employee else None
        if account is None or message.text.strip() != account.login:
            await message.answer("Login noto'g'ri.")
            await state.clear()
            return
    await state.set_state(AuditAuth.password)
    await message.answer("Parol kiriting:")


@router.message(AuditAuth.password, F.text)
async def audit_password(message: Message, state: FSMContext) -> None:
    async with async_session() as session:
        employee = await get_employee(session, message.from_user.id)
        account = await get_active_audit_account(session, employee.id) if employee else None
        if account is None or not verify_password(message.text.strip(), account.salt, account.password_hash):
            await message.answer("Parol noto'g'ri.")
            await state.clear()
            return
        reply_keyboard = await reply_keyboard_for_employee(session, employee)
        await apply_bot_commands(message.bot, session, employee)
    await state.clear()
    if reply_keyboard is not None:
        await message.answer("Pastdagi tugmalar yangilandi.", reply_markup=reply_keyboard)
    await message.answer("✅ Kirish muvaffaqiyatli.", reply_markup=audit_menu_keyboard())


@router.callback_query(F.data == "panel_audit")
async def panel_audit_entry(callback: CallbackQuery, state: FSMContext) -> None:
    async with async_session() as session:
        employee = await get_employee(session, callback.from_user.id)
        if employee is None:
            await callback.answer("Avval botga /start bosing.", show_alert=True)
            return
        if employee.is_admin:
            await safe_edit_text(callback.message, "Audit paneli:", reply_markup=audit_menu_keyboard())
            await callback.answer()
            return
        account = await get_active_audit_account(session, employee.id)
        if account is None:
            await callback.answer("Sizga audit huquqi berilmagan.", show_alert=True)
            return
    await state.set_state(AuditAuth.login)
    await safe_edit_text(callback.message, "Login kiriting:")
    await callback.answer()


@router.callback_query(F.data == "audit_menu")
async def back_to_audit_menu(callback: CallbackQuery, state: FSMContext) -> None:
    async with async_session() as session:
        employee = await get_employee(session, callback.from_user.id)
        if not await is_privileged(session, employee):
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
    await state.clear()
    await safe_edit_text(callback.message, "Audit paneli:", reply_markup=audit_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "fine_start")
async def fine_start(callback: CallbackQuery, state: FSMContext) -> None:
    async with async_session() as session:
        employee = await get_employee(session, callback.from_user.id)
        if not await is_privileged(session, employee):
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        employees = [e for e in await list_staff(session) if e.id != employee.id]
    if not employees:
        await callback.answer("Xodimlar ro'yxati bo'sh.", show_alert=True)
        return
    await state.set_state(FineFlow.choosing_employee)
    await safe_edit_text(callback.message,
        "Shtraf beriladigan xodimni tanlang:",
        reply_markup=employees_keyboard(employees, "fine_emp", back_callback="audit_menu"),
    )
    await callback.answer()


@router.message(F.text == BTN_FINE_GIVE)
async def fine_start_msg(message: Message, state: FSMContext) -> None:
    async with async_session() as session:
        employee = await get_employee(session, message.from_user.id)
        if not await is_privileged(session, employee):
            return
        employees = [e for e in await list_staff(session) if e.id != employee.id]
    if not employees:
        await message.answer("Xodimlar ro'yxati bo'sh.")
        return
    await state.set_state(FineFlow.choosing_employee)
    await message.answer(
        "Shtraf beriladigan xodimni tanlang:",
        reply_markup=employees_keyboard(employees, "fine_emp", back_callback="audit_menu"),
    )


@router.callback_query(FineFlow.choosing_employee, F.data.startswith("fine_emp:"))
async def fine_choose_employee(callback: CallbackQuery, state: FSMContext) -> None:
    employee_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        requester = await get_employee(session, callback.from_user.id)
        templates = await visible_fine_templates(session, requester)
    if not templates:
        await callback.answer("Avval shablon qo'shilishi kerak.", show_alert=True)
        return
    await state.update_data(fine_employee_id=employee_id)
    await state.set_state(FineFlow.choosing_template)
    await safe_edit_text(callback.message,
        "Shtraf sababini tanlang:",
        reply_markup=fine_templates_keyboard(templates, "fine_template", back_callback="audit_menu"),
    )
    await callback.answer()


@router.callback_query(FineFlow.choosing_template, F.data.startswith("fine_template:"))
async def fine_choose_template(callback: CallbackQuery, state: FSMContext) -> None:
    template_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        template = await session.get(FineTemplate, template_id)
        if template is None:
            await callback.answer("Shablon topilmadi.", show_alert=True)
            return
        reason = template.text
        photo_required = await get_setting(session, "fine_photo_required", "false")
    await state.update_data(reason=reason)
    await state.set_state(FineFlow.waiting_photo)
    if photo_required == "true":
        await safe_edit_text(callback.message, "Endi shtraf uchun rasm yuboring.")
    else:
        await safe_edit_text(
            callback.message,
            "Xohlasangiz shtraf uchun rasm yuboring (ixtiyoriy):",
            reply_markup=photo_prompt_keyboard(),
        )
    await callback.answer()


@router.callback_query(FineFlow.waiting_photo, F.data == "fine_skip_photo")
async def fine_skip_photo(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(photo_file_id="")
    await state.set_state(FineFlow.waiting_amount)
    await safe_edit_text(callback.message, "Shtraf summasini kiriting (so'm, faqat raqam):")
    await callback.answer()


@router.message(FineFlow.waiting_photo, F.photo)
async def fine_receive_photo(message: Message, state: FSMContext) -> None:
    photo_file_id = message.photo[-1].file_id
    await state.update_data(photo_file_id=photo_file_id)
    await state.set_state(FineFlow.waiting_amount)
    await message.answer("Shtraf summasini kiriting (so'm, faqat raqam):")


@router.message(FineFlow.waiting_photo)
async def fine_wrong_photo(message: Message) -> None:
    async with async_session() as session:
        photo_required = await get_setting(session, "fine_photo_required", "false")
    if photo_required == "true":
        await message.answer("Iltimos, rasm yuboring.")
    else:
        await message.answer("Iltimos, rasm yuboring yoki yuqoridagi tugma orqali o'tkazib yuboring.")


@router.message(FineFlow.waiting_amount, F.text)
async def fine_receive_amount(message: Message, state: FSMContext) -> None:
    raw = message.text.strip().replace(" ", "")
    if not raw.isdigit():
        await message.answer("Summani faqat raqam bilan kiriting:")
        return
    amount = int(raw)
    data = await state.get_data()
    reason = data["reason"]
    async with async_session() as session:
        issued_by = await get_employee(session, message.from_user.id)
        employee = await session.get(Employee, data["fine_employee_id"])
        if employee is None or issued_by is None:
            await state.clear()
            await message.answer("Xatolik yuz berdi, qaytadan urinib ko'ring.")
            return
        session.add(
            Fine(
                employee_id=employee.id,
                issued_by_id=issued_by.id,
                amount=amount,
                reason=reason,
                photo_file_id=data["photo_file_id"],
            )
        )
        await session.commit()
        employee_name = employee.full_name
        employee_tg_id = employee.telegram_id
        issued_by_name = issued_by.full_name
        photo_file_id = data["photo_file_id"]
        admins = await list_admins(session)
    await state.clear()
    amount_str = f"{amount:,}".replace(",", " ")
    await message.answer(
        f"✅ Shtraf berildi: {employee_name} — {amount_str} so'm ({reason})",
        reply_markup=audit_menu_keyboard(),
    )
    employee_caption = f"Sizga shtraf berildi.\nSabab: {reason}\nSumma: {amount_str} so'm"
    try:
        if photo_file_id:
            await message.bot.send_photo(employee_tg_id, photo=photo_file_id, caption=employee_caption)
        else:
            await message.bot.send_message(employee_tg_id, employee_caption)
    except Exception:
        pass

    admin_caption = (
        f"\U0001f4cc {issued_by_name} tomonidan shtraf berildi:\n"
        f"Xodim: {employee_name}\n"
        f"Sabab: {reason}\n"
        f"Summa: {amount_str} so'm"
    )
    for admin in admins:
        try:
            if photo_file_id:
                await message.bot.send_photo(admin.telegram_id, photo=photo_file_id, caption=admin_caption)
            else:
                await message.bot.send_message(admin.telegram_id, admin_caption)
        except Exception:
            continue


async def _employee_fine_totals(session, employees: list[Employee]) -> dict[int, tuple[int, int]]:
    if not employees:
        return {}
    result = await session.execute(
        select(Fine.employee_id, func.coalesce(func.sum(Fine.amount), 0), func.count(Fine.id))
        .where(Fine.employee_id.in_([e.id for e in employees]))
        .group_by(Fine.employee_id)
    )
    return {row[0]: (row[1], row[2]) for row in result.all()}


@router.callback_query(F.data == "report_start")
async def report_start(callback: CallbackQuery, state: FSMContext) -> None:
    async with async_session() as session:
        employee = await get_employee(session, callback.from_user.id)
        if not await is_privileged(session, employee):
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        employees = await list_employees_with_fines(session)
        if not employees:
            await callback.answer("Hozircha shtraflar yo'q.", show_alert=True)
            return
        totals = await _employee_fine_totals(session, employees)
    grand_total = sum(amount for amount, _ in totals.values())
    grand_total_str = f"{grand_total:,}".replace(",", " ")
    await state.set_state(ReportFlow.choosing_employee)
    await safe_edit_text(callback.message,
        f"\U0001f4ca Shtraflar hisoboti — jami: {grand_total_str} so'm\n\n"
        "Batafsil tarix uchun xodimni tanlang:",
        reply_markup=fine_totals_keyboard(employees, totals, back_callback="audit_menu"),
    )
    await callback.answer()


@router.message(F.text.in_({"/hisobot", BTN_FINE_REPORT}))
async def hisobot_command(message: Message, state: FSMContext) -> None:
    async with async_session() as session:
        employee = await get_employee(session, message.from_user.id)
        if not await is_privileged(session, employee):
            return
        employees = await list_employees_with_fines(session)
        if not employees:
            await message.answer("Hozircha shtraflar yo'q.")
            return
        totals = await _employee_fine_totals(session, employees)
    grand_total = sum(amount for amount, _ in totals.values())
    grand_total_str = f"{grand_total:,}".replace(",", " ")
    await state.set_state(ReportFlow.choosing_employee)
    await message.answer(
        f"\U0001f4ca Shtraflar hisoboti — jami: {grand_total_str} so'm\n\n"
        "Batafsil tarix uchun xodimni tanlang:",
        reply_markup=fine_totals_keyboard(employees, totals, back_callback="audit_menu"),
    )


@router.callback_query(ReportFlow.choosing_employee, F.data.startswith("report_emp:"))
async def report_show(callback: CallbackQuery, state: FSMContext) -> None:
    employee_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        employee = await session.get(Employee, employee_id)
        result = await session.execute(
            select(Fine).where(Fine.employee_id == employee_id).order_by(Fine.created_at.desc())
        )
        fines = result.scalars().all()
        total_result = await session.execute(
            select(func.coalesce(func.sum(Fine.amount), 0)).where(Fine.employee_id == employee_id)
        )
        total = total_result.scalar_one()
    await state.clear()
    if not fines:
        await safe_edit_text(callback.message,
            f"{employee.full_name} uchun shtraflar topilmadi.", reply_markup=audit_menu_keyboard()
        )
        await callback.answer()
        return
    total_str = f"{total:,}".replace(",", " ")
    lines = [f"\U0001f4ca {employee.full_name} — jami: {total_str} so'm", ""]
    for fine in fines:
        amount_str = f"{fine.amount:,}".replace(",", " ")
        lines.append(f"• {fine.created_at:%d.%m.%Y %H:%M} — {amount_str} so'm ({fine.reason})")
    await safe_edit_text(callback.message, "\n".join(lines), reply_markup=audit_menu_keyboard())
    await callback.answer()


async def _audit_owned_templates(session) -> list[FineTemplate]:
    result = await session.execute(
        select(FineTemplate).where(FineTemplate.owner == "audit").order_by(FineTemplate.short_name)
    )
    return list(result.scalars().all())


@router.callback_query(F.data == "audit_templates_menu")
async def audit_templates_menu(callback: CallbackQuery) -> None:
    async with async_session() as session:
        employee = await get_employee(session, callback.from_user.id)
        if not await is_privileged(session, employee):
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        templates = await _audit_owned_templates(session)
    await safe_edit_text(
        callback.message,
        "Mening shablonlarim:",
        reply_markup=audit_templates_manage_keyboard(templates, back_callback="audit_menu"),
    )
    await callback.answer()


@router.message(F.text == BTN_MY_TEMPLATES)
async def audit_templates_menu_msg(message: Message) -> None:
    async with async_session() as session:
        employee = await get_employee(session, message.from_user.id)
        if not await is_privileged(session, employee):
            return
        templates = await _audit_owned_templates(session)
    await message.answer(
        "Mening shablonlarim:",
        reply_markup=audit_templates_manage_keyboard(templates, back_callback="audit_menu"),
    )


@router.callback_query(F.data.startswith("toggle_audit_template:"))
async def toggle_audit_template(callback: CallbackQuery) -> None:
    template_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        employee = await get_employee(session, callback.from_user.id)
        if not await is_privileged(session, employee):
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        template = await session.get(FineTemplate, template_id)
        if template is None or template.owner != "audit":
            await callback.answer("Shablon topilmadi.", show_alert=True)
            return
        template.is_active = not template.is_active
        await session.commit()
        templates = await _audit_owned_templates(session)
    await safe_edit_text(
        callback.message,
        "Mening shablonlarim:",
        reply_markup=audit_templates_manage_keyboard(templates, back_callback="audit_menu"),
    )
    await callback.answer()


@router.callback_query(F.data == "new_audit_template")
async def new_audit_template_start(callback: CallbackQuery, state: FSMContext) -> None:
    async with async_session() as session:
        employee = await get_employee(session, callback.from_user.id)
        if not await is_privileged(session, employee):
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
    await state.update_data(template_owner="audit")
    await state.set_state(NewFineTemplate.text)
    await callback.message.answer("Yangi shablon matnini kiriting:")
    await callback.answer()
