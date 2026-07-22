from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database import async_session
from keyboards import (
    admin_menu_keyboard,
    audit_account_detail_keyboard,
    audit_accounts_keyboard,
    employees_keyboard,
    fine_templates_manage_keyboard,
    roles_keyboard,
    roles_manage_keyboard,
)
from models import AuditAccount, Employee, FineTemplate, Role
from states import NewAudit, NewFineTemplate, NewRole, ReportFlow, ResetAuditPassword
from utils import get_employee, hash_password, list_employees_with_fines, list_workers

router = Router(name="admin")


async def _require_admin(session, telegram_id: int) -> Employee | None:
    employee = await get_employee(session, telegram_id)
    return employee if employee and employee.is_admin else None


@router.message(F.text == "/ishchilar")
async def list_employees(message: Message) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, message.from_user.id)
        if not admin:
            return
        employees = await list_workers(session)
        if not employees:
            await message.answer("Hozircha botga start bergan xodimlar yo'q.")
            return
        await message.answer(
            "Xodimlar ro'yxati (rol berish uchun tanlang):",
            reply_markup=employees_keyboard(employees, "assign_role", back_callback="adm_menu"),
        )


@router.callback_query(F.data.startswith("assign_role:"))
async def choose_role_for_employee(callback: CallbackQuery) -> None:
    employee_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        admin = await _require_admin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        result = await session.execute(select(Role).where(Role.is_active.is_(True)).order_by(Role.name))
        roles = result.scalars().all()
        if not roles:
            await callback.answer("Avval /rollar orqali rol qo'shing.", show_alert=True)
            return
        await callback.message.edit_text(
            "Rolni tanlang:",
            reply_markup=roles_keyboard(roles, f"set_role:{employee_id}", include_remove=True),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("set_role:"))
async def set_role(callback: CallbackQuery) -> None:
    _, employee_id, role_id = callback.data.split(":")
    employee_id, role_id = int(employee_id), int(role_id)
    async with async_session() as session:
        admin = await _require_admin(session, callback.from_user.id)
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
            await callback.message.edit_text(f"{employee.full_name} uchun rol olib tashlandi.")
            try:
                await callback.bot.send_message(employee.telegram_id, "Sizning rolingiz olib tashlandi.")
            except Exception:
                pass
        else:
            role = await session.get(Role, role_id)
            if role is None:
                await callback.answer("Rol topilmadi.", show_alert=True)
                return
            employee.role_id = role.id
            await session.commit()
            await callback.message.edit_text(f"{employee.full_name} uchun rol berildi: {role.name}")
            try:
                await callback.bot.send_message(employee.telegram_id, f"Sizga '{role.name}' roli berildi.")
            except Exception:
                pass
    await callback.answer()


@router.message(F.text == "/rollar")
async def manage_roles(message: Message) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, message.from_user.id)
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
        admin = await _require_admin(session, callback.from_user.id)
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
        await callback.message.edit_text(
            "Rollarni boshqarish:", reply_markup=roles_manage_keyboard(roles, back_callback="adm_menu")
        )
    await callback.answer()


@router.callback_query(F.data == "new_role")
async def new_role_start(callback: CallbackQuery, state: FSMContext) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
    await state.set_state(NewRole.name)
    await callback.message.answer("Yangi rol nomini kiriting:")
    await callback.answer()


@router.message(NewRole.name, F.text)
async def new_role_save(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name:
        await message.answer("Rol nomi bo'sh bo'lishi mumkin emas. Qayta kiriting:")
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


@router.message(F.text == "/auditlar")
async def list_audit_accounts(message: Message) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, message.from_user.id)
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
        admin = await _require_admin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        account = await session.get(AuditAccount, account_id)
        if account is None:
            await callback.answer("Akkaunt topilmadi.", show_alert=True)
            return
        text = await _audit_detail_text(session, account)
    await callback.message.edit_text(
        text, reply_markup=audit_account_detail_keyboard(account, back_callback="adm_audits")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_audit:"))
async def toggle_audit(callback: CallbackQuery) -> None:
    account_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        admin = await _require_admin(session, callback.from_user.id)
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
    await callback.message.edit_text(
        text, reply_markup=audit_account_detail_keyboard(account, back_callback="adm_audits")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("reset_audit_pwd:"))
async def reset_audit_password_start(callback: CallbackQuery, state: FSMContext) -> None:
    account_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        admin = await _require_admin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        account = await session.get(AuditAccount, account_id)
        if account is None:
            await callback.answer("Akkaunt topilmadi.", show_alert=True)
            return
    await state.update_data(reset_account_id=account_id)
    await state.set_state(ResetAuditPassword.password)
    await callback.message.edit_text("Yangi parolni kiriting (kamida 4 belgi):")
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
        admin = await _require_admin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        employees = await list_workers(session)
    if not employees:
        await callback.answer("Avval /ishchilar ro'yxatida xodim bo'lishi kerak.", show_alert=True)
        return
    await state.set_state(NewAudit.choosing_employee)
    await callback.message.edit_text(
        "Audit huquqi beriladigan xodimni tanlang:",
        reply_markup=employees_keyboard(employees, "new_audit_emp"),
    )
    await callback.answer()


@router.callback_query(NewAudit.choosing_employee, F.data.startswith("new_audit_emp:"))
async def new_audit_choose_employee(callback: CallbackQuery, state: FSMContext) -> None:
    employee_id = int(callback.data.split(":")[1])
    await state.update_data(audit_employee_id=employee_id)
    await state.set_state(NewAudit.login)
    await callback.message.edit_text("Ushbu xodim uchun login kiriting:")
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
    await message.answer("Endi parol kiriting (kamida 4 belgi):")


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
    await state.clear()
    await message.answer(
        f"✅ Audit akkaunt yaratildi: {employee_name} — login: {data['audit_login']}\n"
        "Login va parolni xodimga o'zingiz yetkazing."
    )


@router.message(F.text == "/shablonlar")
async def manage_fine_templates(message: Message) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, message.from_user.id)
        if not admin:
            return
        templates = await _all_fine_templates(session)
        await message.answer(
            "Shtraf shablonlarini boshqarish:",
            reply_markup=fine_templates_manage_keyboard(templates, back_callback="adm_menu"),
        )


async def _all_fine_templates(session) -> list[FineTemplate]:
    result = await session.execute(select(FineTemplate).order_by(FineTemplate.text))
    return list(result.scalars().all())


@router.callback_query(F.data.startswith("toggle_template:"))
async def toggle_fine_template(callback: CallbackQuery) -> None:
    template_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        admin = await _require_admin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        template = await session.get(FineTemplate, template_id)
        if template is None:
            await callback.answer("Shablon topilmadi.", show_alert=True)
            return
        template.is_active = not template.is_active
        await session.commit()
        templates = await _all_fine_templates(session)
        await callback.message.edit_text(
            "Shtraf shablonlarini boshqarish:",
            reply_markup=fine_templates_manage_keyboard(templates, back_callback="adm_menu"),
        )
    await callback.answer()


@router.callback_query(F.data == "new_template")
async def new_fine_template_start(callback: CallbackQuery, state: FSMContext) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
    await state.set_state(NewFineTemplate.text)
    await callback.message.answer("Yangi shablon matnini kiriting:")
    await callback.answer()


@router.message(NewFineTemplate.text, F.text)
async def new_fine_template_save(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if not text:
        await message.answer("Shablon matni bo'sh bo'lishi mumkin emas. Qayta kiriting:")
        return
    async with async_session() as session:
        existing = await session.execute(select(FineTemplate).where(FineTemplate.text == text))
        if existing.scalar_one_or_none():
            await message.answer("Bu shablon allaqachon mavjud. Boshqa matn kiriting:")
            return
        session.add(FineTemplate(text=text))
        await session.commit()
        templates = await _all_fine_templates(session)
    await state.clear()
    await message.answer(
        f"✅ '{text}' shabloni qo'shildi.",
        reply_markup=fine_templates_manage_keyboard(templates, back_callback="adm_menu"),
    )


@router.callback_query(F.data == "adm_menu")
async def admin_menu(callback: CallbackQuery) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
    await callback.message.edit_text("Admin paneli:", reply_markup=admin_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "adm_workers")
async def list_employees_cb(callback: CallbackQuery) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        employees = await list_workers(session)
    if not employees:
        await callback.message.edit_text(
            "Hozircha botga start bergan xodimlar yo'q.", reply_markup=admin_menu_keyboard()
        )
        await callback.answer()
        return
    await callback.message.edit_text(
        "Xodimlar ro'yxati (rol berish uchun tanlang):",
        reply_markup=employees_keyboard(employees, "assign_role", back_callback="adm_menu"),
    )
    await callback.answer()


@router.callback_query(F.data == "adm_roles")
async def manage_roles_cb(callback: CallbackQuery) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        result = await session.execute(select(Role).order_by(Role.name))
        roles = result.scalars().all()
    await callback.message.edit_text(
        "Rollarni boshqarish:", reply_markup=roles_manage_keyboard(roles, back_callback="adm_menu")
    )
    await callback.answer()


@router.callback_query(F.data == "adm_audits")
async def list_audit_accounts_cb(callback: CallbackQuery) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        accounts = await _all_audit_accounts(session)
    await callback.message.edit_text(
        "Audit akkauntlari:", reply_markup=audit_accounts_keyboard(accounts, back_callback="adm_menu")
    )
    await callback.answer()


@router.callback_query(F.data == "adm_templates")
async def manage_fine_templates_cb(callback: CallbackQuery) -> None:
    async with async_session() as session:
        admin = await _require_admin(session, callback.from_user.id)
        if not admin:
            await callback.answer("Sizda ruxsat yo'q.", show_alert=True)
            return
        templates = await _all_fine_templates(session)
    await callback.message.edit_text(
        "Shtraf shablonlarini boshqarish:",
        reply_markup=fine_templates_manage_keyboard(templates, back_callback="adm_menu"),
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
    await callback.message.edit_text(
        "Hisobot uchun xodimni tanlang:",
        reply_markup=employees_keyboard(employees, "report_emp", back_callback="adm_menu"),
    )
    await callback.answer()
