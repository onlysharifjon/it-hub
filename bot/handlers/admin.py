import asyncio

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database import async_session
from keyboards import (
    BTN_AUDIT_ACCOUNTS,
    BTN_BROADCAST,
    BTN_REPORTS,
    BTN_ROLES,
    BTN_SETTINGS,
    BTN_TEMPLATES,
    BTN_WORKERS,
    admin_menu_keyboard,
    admin_templates_keyboard,
    admin_tier_keyboard,
    audit_account_detail_keyboard,
    audit_accounts_keyboard,
    audit_templates_manage_keyboard,
    broadcast_choice_keyboard,
    broadcast_confirm_keyboard,
    broadcast_prompt_keyboard,
    broadcast_role_keyboard,
    cancel_keyboard,
    employees_keyboard,
    invite_tier_keyboard,
    reports_choice_keyboard,
    roles_keyboard,
    roles_manage_keyboard,
    settings_choice_keyboard,
    template_detail_keyboard,
)
from models import AuditAccount, Employee, FineTemplate, Role
from states import (
    Broadcast,
    EditFineTemplate,
    NewAudit,
    NewFineTemplate,
    NewRole,
    ReportFlow,
    ResetAuditPassword,
)
from utils import (
    apply_bot_commands,
    create_invite_link,
    ensure_audit_account,
    get_employee,
    get_setting,
    hash_password,
    list_admins,
    list_employees_with_fines,
    list_parents,
    list_staff,
    list_staff_without_audit,
    list_workers,
    reply_keyboard_for_employee,
    safe_edit_text,
    set_setting,
)

router = Router(name="admin")


async def _require_admin(session, telegram_id: int) -> Employee | None:
    employee = await get_employee(session, telegram_id)
    return employee if employee and employee.is_admin else None


async def _require_superadmin(session, telegram_id: int) -> Employee | None:
    employee = await get_employee(session, telegram_id)
    return employee if employee and employee.is_admin and employee.is_superadmin else None


@router.message(F.text.in_({"/ishchilar", BTN_WORKERS}))
async def list_employees(message: Message) -> None:
    async with async_session() as session:
        admin = await _require_superadmin(session, message.from_user.id)
        if not admin:
            return
        employees = await list_staff_without_audit(session)
        if not employees:
            await message.answer("Hozircha botga start bergan xodimlar yo'q.")
            return
        await message.answer(
            f"\U0001f465 Xodimlar ro'yxati — jami {len(employees)} kishi\n\nRol berish uchun xodimni tanlang:",
            reply_markup=employees_keyboard(employees, "assign_role", back_callback="adm_menu"),
        )


@router.callback_query(F.data.startswith("assign_role:"))
async def choose_role_for_employee(callback: CallbackQuery) -> None:
    employee_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        result = await session.execute(select(Role).where(Role.is_active.is_(True)).order_by(Role.name))
        roles = result.scalars().all()
        if not roles:
            await callback.answer("Avval /rollar orqali rol qo'shing.", show_alert=True)
            return
        await safe_edit_text(callback.message,
            "Rolni tanlang:",
            reply_markup=roles_keyboard(roles, f"set_role:{employee_id}", include_remove=True),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("set_role:"))
async def set_role(callback: CallbackQuery) -> None:
    _, employee_id, role_id = callback.data.split(":")
    employee_id, role_id = int(employee_id), int(role_id)
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        employee = await session.get(Employee, employee_id)
        if employee is None:
            await callback.answer("Xodim topilmadi.", show_alert=True)
            return
        if role_id == 0:
            employee.role_id = None
            await session.commit()
            await safe_edit_text(callback.message, f"{employee.full_name} uchun rol olib tashlandi.")
            try:
                keyboard = await reply_keyboard_for_employee(session, employee)
                await callback.bot.send_message(
                    employee.telegram_id, "Sizning rolingiz olib tashlandi.", reply_markup=keyboard
                )
            except Exception:
                pass
        else:
            role = await session.get(Role, role_id)
            if role is None:
                await callback.answer("Rol topilmadi.", show_alert=True)
                return
            employee.role_id = role.id
            await session.commit()
            await safe_edit_text(callback.message, f"{employee.full_name} uchun rol berildi: {role.name}")
            try:
                keyboard = await reply_keyboard_for_employee(session, employee)
                await callback.bot.send_message(
                    employee.telegram_id,
                    f"Sizga '{role.name}' roli berildi. Pastdagi tugmalar orqali davom eting.",
                    reply_markup=keyboard,
                )
            except Exception:
                pass
        await apply_bot_commands(callback.bot, session, employee)
    await callback.answer()


@router.message(F.text.in_({"/rollar", BTN_ROLES}))
async def manage_roles(message: Message) -> None:
    async with async_session() as session:
        admin = await _require_superadmin(session, message.from_user.id)
        if not admin:
            return
        result = await session.execute(select(Role).order_by(Role.name))
        roles = result.scalars().all()
        await message.answer(
            "Rollarni boshqarish:", reply_markup=roles_manage_keyboard(roles, back_callback="adm_menu")
        )


@router.callback_query(F.data.startswith("toggle_role:"))
async def toggle_role(callback: CallbackQuery) -> None:
    role_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        role = await session.get(Role, role_id)
        if role is None:
            await callback.answer("Rol topilmadi.", show_alert=True)
            return
        role.is_active = not role.is_active
        await session.commit()
        result = await session.execute(select(Role).order_by(Role.name))
        roles = result.scalars().all()
        await safe_edit_text(callback.message,
            "Rollarni boshqarish:", reply_markup=roles_manage_keyboard(roles, back_callback="adm_menu")
        )
    await callback.answer()


@router.callback_query(F.data == "new_role")
async def new_role_start(callback: CallbackQuery, state: FSMContext) -> None:
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
    await state.set_state(NewRole.name)
    await callback.message.answer("Yangi rol nomini kiriting:", reply_markup=cancel_keyboard("adm_menu"))
    await callback.answer()


@router.message(NewRole.name, F.text)
async def new_role_save(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name:
        await message.answer("Rol nomi bo'sh bo'lishi mumkin emas. Qayta kiriting:")
        return
    if len(name) > 64:
        await message.answer("Rol nomi 64 belgidan oshmasligi kerak. Qayta kiriting:")
        return
    async with async_session() as session:
        existing = await session.execute(select(Role).where(Role.name == name))
        if existing.scalar_one_or_none():
            await message.answer("Bu nomdagi rol allaqachon mavjud. Boshqa nom kiriting:")
            return
        session.add(Role(name=name))
        await session.commit()
        result = await session.execute(select(Role).order_by(Role.name))
        roles = result.scalars().all()
    await state.clear()
    await message.answer(
        f"✅ '{name}' roli qo'shildi.", reply_markup=roles_manage_keyboard(roles, back_callback="adm_menu")
    )


@router.message(F.text.in_({"/auditlar", BTN_AUDIT_ACCOUNTS}))
async def list_audit_accounts(message: Message) -> None:
    async with async_session() as session:
        admin = await _require_superadmin(session, message.from_user.id)
        if not admin:
            return
        accounts = await _all_audit_accounts(session)
        await message.answer(
            "Audit akkauntlari:", reply_markup=audit_accounts_keyboard(accounts, back_callback="adm_menu")
        )


async def _all_audit_accounts(session) -> list[AuditAccount]:
    result = await session.execute(
        select(AuditAccount).options(selectinload(AuditAccount.employee)).order_by(AuditAccount.login)
    )
    return list(result.scalars().all())


async def _audit_detail_text(session, account: AuditAccount) -> str:
    employee = await session.get(Employee, account.employee_id)
    status = "✅ Faol" if account.is_active else "\U0001f6ab Nofaol"
    return (
        f"\U0001f464 {employee.full_name if employee else '?'}\n"
        f"Login: <code>{account.login}</code>\n"
        f"Holat: {status}"
    )


@router.callback_query(F.data.startswith("audit_detail:"))
async def audit_detail(callback: CallbackQuery) -> None:
    account_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        account = await session.get(AuditAccount, account_id)
        if account is None:
            await callback.answer("Akkaunt topilmadi.", show_alert=True)
            return
        text = await _audit_detail_text(session, account)
    await safe_edit_text(callback.message,
        text, reply_markup=audit_account_detail_keyboard(account, back_callback="adm_audits")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_audit:"))
async def toggle_audit(callback: CallbackQuery) -> None:
    account_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        account = await session.get(AuditAccount, account_id)
        if account is None:
            await callback.answer("Akkaunt topilmadi.", show_alert=True)
            return
        account.is_active = not account.is_active
        await session.commit()
        text = await _audit_detail_text(session, account)
    await safe_edit_text(callback.message,
        text, reply_markup=audit_account_detail_keyboard(account, back_callback="adm_audits")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("reset_audit_pwd:"))
async def reset_audit_password_start(callback: CallbackQuery, state: FSMContext) -> None:
    account_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        account = await session.get(AuditAccount, account_id)
        if account is None:
            await callback.answer("Akkaunt topilmadi.", show_alert=True)
            return
    await state.update_data(reset_account_id=account_id)
    await state.set_state(ResetAuditPassword.password)
    await safe_edit_text(
        callback.message,
        "Yangi parolni kiriting (kamida 4 belgi):",
        reply_markup=cancel_keyboard("adm_menu"),
    )
    await callback.answer()


@router.message(ResetAuditPassword.password, F.text)
async def reset_audit_password_save(message: Message, state: FSMContext) -> None:
    password = message.text.strip()
    if len(password) < 4:
        await message.answer("Parol juda qisqa. Kamida 4 belgidan iborat parol kiriting:")
        return
    data = await state.get_data()
    password_hash, salt = hash_password(password)
    async with async_session() as session:
        account = await session.get(AuditAccount, data["reset_account_id"])
        if account is None:
            await state.clear()
            await message.answer("Akkaunt topilmadi.")
            return
        account.password_hash = password_hash
        account.salt = salt
        await session.commit()
        text = await _audit_detail_text(session, account)
    await state.clear()
    await message.answer(
        f"✅ Parol yangilandi.\n\n{text}",
        reply_markup=audit_account_detail_keyboard(account, back_callback="adm_audits"),
    )


@router.callback_query(F.data == "new_audit")
async def new_audit_start(callback: CallbackQuery, state: FSMContext) -> None:
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        employees = await list_staff_without_audit(session)
    if not employees:
        await callback.answer("Avval /ishchilar ro'yxatida xodim bo'lishi kerak.", show_alert=True)
        return
    await state.set_state(NewAudit.choosing_employee)
    await safe_edit_text(callback.message,
        "Audit huquqi beriladigan xodimni tanlang:",
        reply_markup=employees_keyboard(employees, "new_audit_emp"),
    )
    await callback.answer()


@router.callback_query(NewAudit.choosing_employee, F.data.startswith("new_audit_emp:"))
async def new_audit_choose_employee(callback: CallbackQuery, state: FSMContext) -> None:
    employee_id = int(callback.data.split(":")[1])
    await state.update_data(audit_employee_id=employee_id)
    await state.set_state(NewAudit.login)
    await safe_edit_text(
        callback.message, "Ushbu xodim uchun login kiriting:", reply_markup=cancel_keyboard("adm_menu")
    )
    await callback.answer()


@router.message(NewAudit.login, F.text)
async def new_audit_login(message: Message, state: FSMContext) -> None:
    login = message.text.strip()
    if not login:
        await message.answer("Login bo'sh bo'lishi mumkin emas. Qayta kiriting:")
        return
    data = await state.get_data()
    async with async_session() as session:
        result = await session.execute(
            select(AuditAccount).where(
                AuditAccount.login == login, AuditAccount.employee_id != data["audit_employee_id"]
            )
        )
        if result.scalar_one_or_none():
            await message.answer("Bu login band. Boshqa login kiriting:")
            return
    await state.update_data(audit_login=login)
    await state.set_state(NewAudit.password)
    await message.answer("Endi parol kiriting (kamida 4 belgi):", reply_markup=cancel_keyboard("adm_menu"))


@router.message(NewAudit.password, F.text)
async def new_audit_password(message: Message, state: FSMContext) -> None:
    password = message.text.strip()
    if len(password) < 4:
        await message.answer("Parol juda qisqa. Kamida 4 belgidan iborat parol kiriting:")
        return
    data = await state.get_data()
    password_hash, salt = hash_password(password)
    async with async_session() as session:
        employee = await session.get(Employee, data["audit_employee_id"])
        if employee is None:
            await state.clear()
            await message.answer("Xodim topilmadi.")
            return
        result = await session.execute(
            select(AuditAccount).where(AuditAccount.employee_id == employee.id)
        )
        account = result.scalar_one_or_none()
        if account is None:
            account = AuditAccount(employee_id=employee.id, login=data["audit_login"])
            session.add(account)
        else:
            account.login = data["audit_login"]
        account.password_hash = password_hash
        account.salt = salt
        account.is_active = True
        await session.commit()
        employee_name = employee.full_name
        await apply_bot_commands(message.bot, session, employee)
        try:
            keyboard = await reply_keyboard_for_employee(session, employee)
            await message.bot.send_message(
                employee.telegram_id,
                "Sizga audit huquqi berildi. Pastdagi tugmalar orqali davom eting.",
                reply_markup=keyboard,
            )
        except Exception:
            pass
    await state.clear()
    await message.answer(
        f"✅ Audit akkaunt yaratildi: {employee_name} — login: {data['audit_login']}\n"
        "Login va parolni xodimga o'zingiz yetkazing."
    )


@router.message(F.text.in_({"/shablonlar", BTN_TEMPLATES}))
async def manage_fine_templates(message: Message) -> None:
    async with async_session() as session:
        admin = await _require_superadmin(session, message.from_user.id)
        if not admin:
            return
        templates = await _admin_fine_templates(session)
        await message.answer(
            "Shtraf shablonlarini boshqarish:",
            reply_markup=admin_templates_keyboard(templates, back_callback="adm_menu"),
        )


async def _admin_fine_templates(session) -> list[FineTemplate]:
    result = await session.execute(
        select(FineTemplate).where(FineTemplate.owner == "admin").order_by(FineTemplate.short_name)
    )
    return list(result.scalars().all())


def _template_detail_text(template: FineTemplate) -> str:
    status = "✅ Faol" if template.is_active else "\U0001f6ab Nofaol"
    shared = "Ha" if template.shared_with_audit else "Yo'q"
    return (
        f"\U0001f4dd {template.short_name}\n"
        f"To'liq matn: {template.text}\n"
        f"Holat: {status}\n"
        f"Auditga ko'rinadimi: {shared}"
    )


@router.callback_query(F.data.startswith("template_detail:"))
async def template_detail(callback: CallbackQuery) -> None:
    template_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        template = await session.get(FineTemplate, template_id)
        if template is None:
            await callback.answer("Shablon topilmadi.", show_alert=True)
            return
        text = _template_detail_text(template)
    await safe_edit_text(
        callback.message, text, reply_markup=template_detail_keyboard(template, back_callback="adm_templates")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_template:"))
async def toggle_fine_template(callback: CallbackQuery) -> None:
    template_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        template = await session.get(FineTemplate, template_id)
        if template is None:
            await callback.answer("Shablon topilmadi.", show_alert=True)
            return
        template.is_active = not template.is_active
        await session.commit()
        text = _template_detail_text(template)
    await safe_edit_text(
        callback.message, text, reply_markup=template_detail_keyboard(template, back_callback="adm_templates")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_template_share:"))
async def toggle_template_share(callback: CallbackQuery) -> None:
    template_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        template = await session.get(FineTemplate, template_id)
        if template is None:
            await callback.answer("Shablon topilmadi.", show_alert=True)
            return
        template.shared_with_audit = not template.shared_with_audit
        await session.commit()
        text = _template_detail_text(template)
    await safe_edit_text(
        callback.message, text, reply_markup=template_detail_keyboard(template, back_callback="adm_templates")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_template:"))
async def edit_template_start(callback: CallbackQuery, state: FSMContext) -> None:
    template_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        template = await session.get(FineTemplate, template_id)
        if template is None:
            await callback.answer("Shablon topilmadi.", show_alert=True)
            return
        current_text = template.text
    await state.update_data(edit_template_id=template_id)
    await state.set_state(EditFineTemplate.text)
    await callback.message.answer(
        f"Hozirgi matn:\n{current_text}\n\nYangi matnni kiriting:",
        reply_markup=cancel_keyboard("adm_menu"),
    )
    await callback.answer()


@router.message(EditFineTemplate.text, F.text)
async def edit_template_save(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if not text:
        await message.answer("Shablon matni bo'sh bo'lishi mumkin emas. Qayta kiriting:")
        return
    data = await state.get_data()
    template_id = data["edit_template_id"]
    async with async_session() as session:
        template = await session.get(FineTemplate, template_id)
        if template is None:
            await state.clear()
            await message.answer("Shablon topilmadi.")
            return
        existing = await session.execute(
            select(FineTemplate).where(
                FineTemplate.text == text,
                FineTemplate.owner == template.owner,
                FineTemplate.id != template_id,
            )
        )
        if existing.scalar_one_or_none():
            await message.answer("Bu shablon matni allaqachon mavjud. Boshqa matn kiriting:")
            return
        template.text = text
        await session.commit()
        detail_text = _template_detail_text(template)
        keyboard = template_detail_keyboard(template, back_callback="adm_templates")
    await state.clear()
    await message.answer("✅ Shablon matni yangilandi.")
    await message.answer(detail_text, reply_markup=keyboard)


@router.callback_query(F.data == "new_template")
async def new_fine_template_start(callback: CallbackQuery, state: FSMContext) -> None:
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
    await state.update_data(template_owner="admin")
    await state.set_state(NewFineTemplate.text)
    await callback.message.answer(
        "Yangi shablon matnini kiriting:", reply_markup=cancel_keyboard("adm_menu")
    )
    await callback.answer()


@router.message(NewFineTemplate.text, F.text)
async def new_fine_template_text(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    data = await state.get_data()
    owner = data.get("template_owner", "admin")
    cancel_target = "adm_menu" if owner == "admin" else "audit_menu"
    if not text:
        await message.answer("Shablon matni bo'sh bo'lishi mumkin emas. Qayta kiriting:")
        return
    async with async_session() as session:
        existing = await session.execute(
            select(FineTemplate).where(FineTemplate.text == text, FineTemplate.owner == owner)
        )
        if existing.scalar_one_or_none():
            await message.answer("Bu shablon allaqachon mavjud. Boshqa matn kiriting:")
            return
    await state.update_data(template_text=text)
    await state.set_state(NewFineTemplate.short_name)
    await message.answer(
        "Endi qisqa nom kiriting (tugmada ko'rinadi, masalan: 'Kechikish'):",
        reply_markup=cancel_keyboard(cancel_target),
    )


@router.message(NewFineTemplate.short_name, F.text)
async def new_fine_template_save(message: Message, state: FSMContext) -> None:
    short_name = message.text.strip()
    if not short_name or len(short_name) > 32:
        await message.answer("Qisqa nom 1-32 belgidan iborat bo'lishi kerak. Qayta kiriting:")
        return
    data = await state.get_data()
    owner = data["template_owner"]
    async with async_session() as session:
        session.add(FineTemplate(text=data["template_text"], short_name=short_name, owner=owner))
        await session.commit()
    await state.clear()
    if owner == "admin":
        async with async_session() as session:
            templates = await _admin_fine_templates(session)
        await message.answer(
            f"✅ '{short_name}' shabloni qo'shildi.",
            reply_markup=admin_templates_keyboard(templates, back_callback="adm_menu"),
        )
    else:
        async with async_session() as session:
            result = await session.execute(
                select(FineTemplate).where(FineTemplate.owner == "audit").order_by(FineTemplate.short_name)
            )
            templates = list(result.scalars().all())
        await message.answer(
            f"✅ '{short_name}' shabloni qo'shildi.",
            reply_markup=audit_templates_manage_keyboard(templates, back_callback="audit_menu"),
        )


@router.callback_query(F.data == "adm_menu")
async def admin_menu(callback: CallbackQuery, state: FSMContext) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
    await state.clear()
    await safe_edit_text(
        callback.message,
        "Admin paneli:\n\n"
        "CRM komandalari: /otaona /davomat /tolov /tolovhisoboti /otaonaid /rasmsozlama",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "adm_workers")
async def list_employees_cb(callback: CallbackQuery) -> None:
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        employees = await list_staff_without_audit(session)
    if not employees:
        await safe_edit_text(callback.message,
            "Hozircha botga start bergan xodimlar yo'q.", reply_markup=admin_menu_keyboard()
        )
        await callback.answer()
        return
    await safe_edit_text(callback.message,
        "Xodimlar ro'yxati (rol berish uchun tanlang):",
        reply_markup=employees_keyboard(employees, "assign_role", back_callback="adm_menu"),
    )
    await callback.answer()


@router.callback_query(F.data == "adm_roles")
async def manage_roles_cb(callback: CallbackQuery) -> None:
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        result = await session.execute(select(Role).order_by(Role.name))
        roles = result.scalars().all()
    await safe_edit_text(callback.message,
        "Rollarni boshqarish:", reply_markup=roles_manage_keyboard(roles, back_callback="adm_menu")
    )
    await callback.answer()


@router.callback_query(F.data == "adm_audits")
async def list_audit_accounts_cb(callback: CallbackQuery) -> None:
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        accounts = await _all_audit_accounts(session)
    await safe_edit_text(callback.message,
        "Audit akkauntlari:", reply_markup=audit_accounts_keyboard(accounts, back_callback="adm_menu")
    )
    await callback.answer()


@router.callback_query(F.data == "adm_templates")
async def manage_fine_templates_cb(callback: CallbackQuery) -> None:
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        templates = await _admin_fine_templates(session)
    await safe_edit_text(
        callback.message,
        "Shtraf shablonlarini boshqarish:",
        reply_markup=admin_templates_keyboard(templates, back_callback="adm_menu"),
    )
    await callback.answer()


@router.callback_query(F.data == "adm_report")
async def admin_report_cb(callback: CallbackQuery, state: FSMContext) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        employees = await list_employees_with_fines(session)
    if not employees:
        await callback.answer("Hozircha shtraflar yo'q.", show_alert=True)
        return
    await state.set_state(ReportFlow.choosing_employee)
    await safe_edit_text(callback.message,
        "Hisobot uchun xodimni tanlang:",
        reply_markup=employees_keyboard(employees, "report_emp", back_callback="adm_menu"),
    )
    await callback.answer()


@router.callback_query(F.data == "bc_parents_start")
async def broadcast_parents_start(callback: CallbackQuery, state: FSMContext) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
    await state.update_data(broadcast_target="parents")
    await state.set_state(Broadcast.text)
    await safe_edit_text(callback.message,
        "Ota-onalarga yuboriladigan xabarni kiriting.\n"
        "Matn yozing yoki rasmni izoh bilan yuboring (rasm shart emas).",
        reply_markup=broadcast_prompt_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "bc_workers_start")
async def broadcast_workers_start(callback: CallbackQuery, state: FSMContext) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        result = await session.execute(
            select(Role)
            .where(Role.is_active.is_(True), Role.is_parent.is_(False))
            .order_by(Role.name)
        )
        roles = result.scalars().all()
    await safe_edit_text(
        callback.message,
        "Kimlarga yubormoqchisiz? Kategoriyani tanlang:",
        reply_markup=broadcast_role_keyboard(roles),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("bc_workers_role:"))
async def broadcast_workers_choose_role(callback: CallbackQuery, state: FSMContext) -> None:
    raw = callback.data.split(":")[1]
    role_id = None if raw == "all" else int(raw)
    async with async_session() as session:
        admin = await _require_admin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        role_name = "Barcha xodimlar"
        if role_id is not None:
            role = await session.get(Role, role_id)
            role_name = role.name if role else "Xodimlar"
    await state.update_data(broadcast_target="workers", broadcast_role_id=role_id)
    await state.set_state(Broadcast.text)
    await safe_edit_text(callback.message,
        f"\"{role_name}\" toifasiga yuboriladigan xabarni kiriting.\n"
        "Matn yozing yoki rasmni izoh bilan yuboring (rasm shart emas).",
        reply_markup=broadcast_prompt_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "bc_cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await safe_edit_text(callback.message, "Bekor qilindi.", reply_markup=admin_menu_keyboard())
    await callback.answer()


@router.message(Broadcast.text, F.photo)
async def broadcast_send_photo(message: Message, state: FSMContext) -> None:
    await _broadcast_preview(message, state, photo_file_id=message.photo[-1].file_id, text=message.caption)


@router.message(Broadcast.text, F.text)
async def broadcast_send_text(message: Message, state: FSMContext) -> None:
    await _broadcast_preview(message, state, photo_file_id=None, text=message.text)


@router.message(Broadcast.text)
async def broadcast_send_invalid(message: Message) -> None:
    await message.answer("Matn yozing yoki rasm yuboring.")


async def _broadcast_recipients(session, target: str, role_id: int | None) -> list[Employee]:
    if target == "parents":
        return await list_parents(session)
    recipients = await list_staff(session)
    if role_id is not None:
        recipients = [e for e in recipients if e.role_id == role_id]
    return recipients


async def _broadcast_preview(
    message: Message, state: FSMContext, photo_file_id: str | None, text: str | None
) -> None:
    data = await state.get_data()
    target = data["broadcast_target"]
    role_id = data.get("broadcast_role_id")
    async with async_session() as session:
        recipients = await _broadcast_recipients(session, target, role_id)
    if not recipients:
        label = "ota-onalar" if target == "parents" else "xodimlar"
        await state.clear()
        await message.answer(f"Hozircha {label} ro'yxati bo'sh.", reply_markup=admin_menu_keyboard())
        return
    await state.update_data(broadcast_photo_file_id=photo_file_id or "", broadcast_text=text or "")
    await state.set_state(Broadcast.confirm)
    keyboard = broadcast_confirm_keyboard(len(recipients))
    preview_caption = f"Quyidagi xabar yuboriladi:\n\n{text or ''}"
    if photo_file_id:
        await message.answer_photo(photo=photo_file_id, caption=preview_caption, reply_markup=keyboard)
    else:
        await message.answer(preview_caption, reply_markup=keyboard)


@router.callback_query(Broadcast.confirm, F.data == "bc_confirm_send")
async def broadcast_confirm_send(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    target = data["broadcast_target"]
    role_id = data.get("broadcast_role_id")
    photo_file_id = data.get("broadcast_photo_file_id") or None
    text = data.get("broadcast_text") or None
    async with async_session() as session:
        recipients = await _broadcast_recipients(session, target, role_id)
    await state.clear()
    if not recipients:
        label = "ota-onalar" if target == "parents" else "xodimlar"
        await callback.message.answer(f"Hozircha {label} ro'yxati bo'sh.", reply_markup=admin_menu_keyboard())
        await callback.answer()
        return
    await callback.answer("Yuborilmoqda...")
    sent = 0
    for recipient in recipients:
        try:
            if photo_file_id:
                await callback.bot.send_photo(recipient.telegram_id, photo=photo_file_id, caption=text)
            else:
                await callback.bot.send_message(recipient.telegram_id, text)
            sent += 1
        except Exception:
            continue
        await asyncio.sleep(0.05)
    await callback.message.answer(
        f"✅ Xabar {sent}/{len(recipients)} kishiga yuborildi.", reply_markup=admin_menu_keyboard()
    )


async def _toggle_fine_photo_required(session) -> str:
    current = await get_setting(session, "fine_photo_required", "false")
    new_value = "false" if current == "true" else "true"
    await set_setting(session, "fine_photo_required", new_value)
    return "MAJBURIY" if new_value == "true" else "IXTIYORIY"


@router.message(F.text == "/rasmsozlama")
async def toggle_fine_photo_setting(message: Message) -> None:
    async with async_session() as session:
        admin = await _require_superadmin(session, message.from_user.id)
        if not admin:
            return
        status = await _toggle_fine_photo_required(session)
    await message.answer(f"✅ Endi shtraf berishda rasm yuborish: {status}")


@router.callback_query(F.data == "toggle_fine_photo")
async def toggle_fine_photo_cb(callback: CallbackQuery) -> None:
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        status = await _toggle_fine_photo_required(session)
    await safe_edit_text(callback.message, f"✅ Endi shtraf berishda rasm yuborish: {status}")
    await callback.answer()


@router.message(F.text == BTN_REPORTS)
async def reports_menu(message: Message) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, message.from_user.id)
        if not admin:
            return
    await message.answer("Qaysi hisobotni ko'rmoqchisiz?", reply_markup=reports_choice_keyboard())


@router.message(F.text == BTN_BROADCAST)
async def broadcast_menu(message: Message) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, message.from_user.id)
        if not admin:
            return
    await message.answer("Kimga xabar yubormoqchisiz?", reply_markup=broadcast_choice_keyboard())


@router.message(F.text == BTN_SETTINGS)
async def settings_menu(message: Message) -> None:
    async with async_session() as session:
        admin = await _require_superadmin(session, message.from_user.id)
        if not admin:
            return
    await message.answer("Qaysi sozlamani o'zgartirmoqchisiz?", reply_markup=settings_choice_keyboard())


@router.callback_query(F.data == "new_admin_start")
async def new_admin_start(callback: CallbackQuery) -> None:
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        candidates = await list_workers(session)
    if not candidates:
        await callback.answer("Admin qilib bo'ladigan foydalanuvchi yo'q. Avval u botga /start bosishi kerak.", show_alert=True)
        return
    await safe_edit_text(
        callback.message,
        "Kimni admin qilmoqchisiz?",
        reply_markup=employees_keyboard(candidates, "set_admin_pick", back_callback="adm_menu"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_admin_pick:"))
async def new_admin_pick_tier(callback: CallbackQuery) -> None:
    employee_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        employee = await session.get(Employee, employee_id)
        if employee is None:
            await callback.answer("Foydalanuvchi topilmadi.", show_alert=True)
            return
        employee_name = employee.full_name
    await safe_edit_text(
        callback.message,
        f"{employee_name} qaysi darajada admin bo'lsin?",
        reply_markup=admin_tier_keyboard(employee_id, back_callback="new_admin_start"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_admin_final:"))
async def new_admin_finalize(callback: CallbackQuery) -> None:
    _, employee_id_str, tier = callback.data.split(":")
    employee_id = int(employee_id_str)
    is_superadmin = tier == "superadmin"
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        employee = await session.get(Employee, employee_id)
        if employee is None:
            await callback.answer("Foydalanuvchi topilmadi.", show_alert=True)
            return
        employee.is_admin = True
        employee.is_superadmin = is_superadmin
        await session.commit()
        employee_name = employee.full_name
        employee_telegram_id = employee.telegram_id
        audit_creds = await ensure_audit_account(session, employee)
        await apply_bot_commands(callback.bot, session, employee)
        keyboard = await reply_keyboard_for_employee(session, employee)
    tier_label = "Superadmin (CEO)" if is_superadmin else "Admin"
    try:
        await callback.bot.send_message(
            employee_telegram_id,
            f"\U0001f451 Sizga {tier_label} huquqi berildi. Pastdagi tugmalar orqali boshqaring.",
            reply_markup=keyboard,
        )
    except Exception:
        pass
    confirm_text = f"✅ {employee_name} endi {tier_label}."
    if audit_creds:
        login, password = audit_creds
        confirm_text += f"\n\U0001f511 Audit login: <code>{login}</code>, parol: <code>{password}</code>"
    await safe_edit_text(callback.message, confirm_text, reply_markup=admin_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "remove_admin_start")
async def remove_admin_start(callback: CallbackQuery) -> None:
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        admins = await list_admins(session)
    if len(admins) <= 1:
        await callback.answer("Bu yagona admin, uni adminlikdan olib bo'lmaydi.", show_alert=True)
        return
    await safe_edit_text(
        callback.message,
        "Kimni adminlikdan olmoqchisiz?",
        reply_markup=employees_keyboard(admins, "unset_admin", back_callback="adm_menu"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("unset_admin:"))
async def remove_admin_pick(callback: CallbackQuery) -> None:
    employee_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        admins = await list_admins(session)
        if len(admins) <= 1:
            await callback.answer("Bu yagona admin, uni adminlikdan olib bo'lmaydi.", show_alert=True)
            return
        employee = await session.get(Employee, employee_id)
        if employee is None or not employee.is_admin:
            await callback.answer("Foydalanuvchi topilmadi.", show_alert=True)
            return
        if employee.is_superadmin and sum(1 for a in admins if a.is_superadmin) <= 1:
            await callback.answer("Bu yagona superadmin, uni olib bo'lmaydi.", show_alert=True)
            return
        employee.is_admin = False
        employee.is_superadmin = False
        await session.commit()
        employee_name = employee.full_name
        employee_telegram_id = employee.telegram_id
        await apply_bot_commands(callback.bot, session, employee)
        keyboard = await reply_keyboard_for_employee(session, employee)
    try:
        await callback.bot.send_message(
            employee_telegram_id, "Sizning admin huquqingiz olib tashlandi.", reply_markup=keyboard
        )
    except Exception:
        pass
    await safe_edit_text(
        callback.message, f"✅ {employee_name} endi admin emas.", reply_markup=admin_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "invite_link_start")
async def invite_link_start(callback: CallbackQuery) -> None:
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
    await safe_edit_text(
        callback.message, "Qaysi daraja uchun havola yarataylik?", reply_markup=invite_tier_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("invite_tier:"))
async def invite_link_generate(callback: CallbackQuery) -> None:
    tier = callback.data.split(":")[1]
    async with async_session() as session:
        admin = await _require_superadmin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        token = await create_invite_link(session, tier, admin.id)
    bot_user = await callback.bot.get_me()
    link = f"https://t.me/{bot_user.username}?start=invite_{token}"
    tier_label = "Superadmin (CEO)" if tier == "superadmin" else "Admin"
    await safe_edit_text(
        callback.message,
        f"\U0001f517 {tier_label} uchun bir martalik havola:\n\n{link}\n\n"
        "Bu havolani ishonchli odamga yuboring — u shu havola orqali botga /start bossa, "
        "avtomatik shu darajaga ko'tariladi. Havola faqat bir marta ishlaydi.",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()
