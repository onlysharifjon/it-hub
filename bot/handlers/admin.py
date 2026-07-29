import asyncio

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from database import async_session
from keyboards import (
    BTN_BROADCAST,
    BTN_REPORTS,
    BTN_ROLES,
    BTN_SETTINGS,
    BTN_WORKERS,
    admin_menu_keyboard,
    admin_tier_keyboard,
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
)
from models import Employee, Role
from states import Broadcast, NewRole
from utils import (
    apply_bot_commands,
    create_invite_link,
    get_employee,
    list_admins,
    list_parents,
    list_staff,
    list_workers,
    reply_keyboard_for_employee,
    safe_edit_text,
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
        employees = await list_staff(session)
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
            if role.is_parent:
                dm_text = (
                    f"\U0001f389 Minar Academyga xush kelibsiz, {employee.full_name}!\n\n"
                    "Endi farzandingizning davomati, dars jadvali va boshqa muhim yangiliklardan shu bot "
                    "orqali xabardor bo'lib turasiz. Boshlash uchun pastdagi \"\U0001f517 Farzand biriktirish\" "
                    "tugmasini bosing."
                )
            else:
                dm_text = f"Sizga '{role.name}' roli berildi. Pastdagi tugmalar orqali davom eting."
            try:
                keyboard = await reply_keyboard_for_employee(session, employee)
                await callback.bot.send_message(employee.telegram_id, dm_text, reply_markup=keyboard)
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
        "CRM komandalari: /otaona /davomat /tolov /tolovhisoboti /otaonaid",
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
        employees = await list_staff(session)
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
