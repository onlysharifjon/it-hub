from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from models import Employee, ParentLink, Role

# Doimiy pastki tugmalar tarkibi o'zgarganda shu qiymatni oshiring — bot ishga tushganda
# eski qiymat bilan solishtirib, farq bo'lsa hamma foydalanuvchiga jim (bildirishnomasiz)
# yangilangan tugmalarni qayta yuboradi (main.py: refresh_reply_keyboards_if_changed).
KEYBOARD_VERSION = "5"

# ── Doimiy pastki menyu tugma matnlari (komandalar bilan bir xil ishlaydi) ──────

BTN_WORKERS = "\U0001f465 Xodimlar"
BTN_ROLES = "\U0001f3ad Rollar"
BTN_REPORTS = "\U0001f4ca Hisobotlar"
BTN_BROADCAST = "\U0001f4e2 Xabar yuborish"
BTN_LINK_PARENT = "\U0001f517 Ota-onani biriktirish"
BTN_ATTENDANCE = "\U0001f4cb Davomat"
BTN_PAYMENT = "\U0001f4b0 To'lov holati"
BTN_SETTINGS = "\U00002699 Sozlamalar"

BTN_MY_CHILD = "\U0001f476 Farzandim"
BTN_SCHEDULE = "\U0001f4c5 Jadval"

BTN_REQUEST_CHILD = "\U0001f517 Farzand biriktirish"


def admin_reply_keyboard() -> ReplyKeyboardMarkup:
    """To'liq huquqli — superadmin uchun."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_WORKERS), KeyboardButton(text=BTN_ROLES)],
            [KeyboardButton(text=BTN_ATTENDANCE), KeyboardButton(text=BTN_PAYMENT)],
            [KeyboardButton(text=BTN_LINK_PARENT), KeyboardButton(text=BTN_REPORTS)],
            [KeyboardButton(text=BTN_BROADCAST), KeyboardButton(text=BTN_SETTINGS)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def limited_admin_reply_keyboard() -> ReplyKeyboardMarkup:
    """Oddiy admin — kundalik ishlar: rol/sozlama boshqaruvi yo'q."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_ATTENDANCE), KeyboardButton(text=BTN_PAYMENT)],
            [KeyboardButton(text=BTN_LINK_PARENT), KeyboardButton(text=BTN_REPORTS)],
            [KeyboardButton(text=BTN_BROADCAST)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def parent_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_MY_CHILD), KeyboardButton(text=BTN_SCHEDULE)]],
        resize_keyboard=True,
        is_persistent=True,
    )


def reports_choice_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="\U0001f4b0 To'lov hisoboti", callback_data="rpt_payment")
    builder.adjust(1)
    return builder.as_markup()


def payment_report_choice_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ To'laganlar", callback_data="payrep:paid")
    builder.button(text="\U0001f534 To'lamaganlar", callback_data="payrep:debtors")
    builder.adjust(1)
    return builder.as_markup()


def broadcast_choice_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="\U0001f46a Ota-onalarga", callback_data="bc_parents_start")
    builder.button(text="\U0001f477 Xodimlarga", callback_data="bc_workers_start")
    builder.adjust(1)
    return builder.as_markup()


def settings_choice_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="\U0001f46a Standart ota-ona ID", callback_data="set_default_parent")
    builder.button(text="➕ Yangi admin qo'shish", callback_data="new_admin_start")
    builder.button(text="➖ Adminlikdan olish", callback_data="remove_admin_start")
    builder.button(text="\U0001f517 Admin/CEO havolasi yaratish", callback_data="invite_link_start")
    builder.adjust(1)
    return builder.as_markup()


def admin_tier_keyboard(employee_id: int, back_callback: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="\U0001f464 Oddiy admin", callback_data=f"set_admin_final:{employee_id}:admin")
    builder.button(
        text="\U0001f451 Superadmin (CEO)", callback_data=f"set_admin_final:{employee_id}:superadmin"
    )
    builder.button(text="⬅️ Orqaga", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def invite_tier_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="\U0001f464 Admin havolasi", callback_data="invite_tier:admin")
    builder.button(text="\U0001f451 Superadmin (CEO) havolasi", callback_data="invite_tier:superadmin")
    builder.button(text="⬅️ Orqaga", callback_data="adm_menu")
    builder.adjust(1)
    return builder.as_markup()


def children_keyboard(links: list[ParentLink]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for link in links:
        builder.button(text=link.student_name, callback_data=f"child_detail:{link.id}")
    builder.adjust(1)
    return builder.as_markup()


def employees_keyboard(
    employees: list[Employee], prefix: str, back_callback: str | None = None
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for employee in employees:
        role_part = f" — {employee.role.name}" if employee.role else " — rol yo'q"
        builder.button(
            text=f"\U0001f464 {employee.full_name}{role_part}", callback_data=f"{prefix}:{employee.id}"
        )
    if back_callback:
        builder.button(text="⬅️ Orqaga", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def roles_keyboard(roles: list[Role], prefix: str, include_remove: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for role in roles:
        builder.button(text=role.name, callback_data=f"{prefix}:{role.id}")
    if include_remove:
        builder.button(text="❌ Rolni olib tashlash", callback_data=f"{prefix}:0")
    builder.adjust(1)
    return builder.as_markup()


def roles_manage_keyboard(roles: list[Role], back_callback: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for role in roles:
        status = "✅ Faol" if role.is_active else "\U0001f6ab Nofaol"
        builder.button(text=f"{role.name} — {status}", callback_data=f"toggle_role:{role.id}")
    builder.button(text="➕ Yangi rol qo'shish", callback_data="new_role")
    if back_callback:
        builder.button(text="⬅️ Orqaga", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="\U0001f465 Xodimlar", callback_data="adm_workers")
    builder.button(text="\U0001f3ad Rollar", callback_data="adm_roles")
    builder.button(text="\U0001f4e2 Ota-onalarga xabar", callback_data="bc_parents_start")
    builder.button(text="\U0001f4e2 Xodimlarga xabar", callback_data="bc_workers_start")
    builder.button(text="⬅️ Orqaga", callback_data="panel_root")
    builder.adjust(1)
    return builder.as_markup()


def payment_students_keyboard(members: list[dict], back_callback: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for member in members:
        paid = member.get("paid")
        icon = "✅" if paid is True else ("\U0001f534" if paid is False else "❓")
        builder.button(
            text=f"{icon} {member['student_name']}", callback_data=f"pay_student:{member['student_id']}"
        )
    builder.button(text="⬅️ Orqaga", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def link_source_keyboard(back_callback: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="\U0001f9d1‍\U0001f91d‍\U0001f9d1 Ota-onalar ro'yxatidan", callback_data="linksrc:parents")
    builder.button(text="\U0001f465 Xodimlar ro'yxatidan", callback_data="linksrc:staff")
    builder.button(text="⬅️ Orqaga", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def link_method_keyboard(back_callback: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="\U0001f3eb Guruh orqali", callback_data="linkmethod:group")
    builder.button(text="\U0001f50d Ism bo'yicha qidirish", callback_data="linkmethod:search")
    builder.button(text="⬅️ Orqaga", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def cancel_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data=callback_data)
    builder.adjust(1)
    return builder.as_markup()


def student_search_results_keyboard(
    students: list[dict], prefix: str, back_callback: str
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for idx, student in enumerate(students):
        group_names = student.get("group_names") or []
        group_part = ", ".join(group_names) if group_names else "Guruhsiz"
        builder.button(text=f"{student['full_name']} — {group_part}", callback_data=f"{prefix}:{idx}")
    builder.button(text="⬅️ Orqaga", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def child_link_check_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tekshirish", callback_data="child_link_check")
    builder.adjust(1)
    return builder.as_markup()


def crm_groups_keyboard(groups: list[dict], prefix: str, back_callback: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for group in groups:
        builder.button(text=group["name"], callback_data=f"{prefix}:{group['id']}")
    builder.button(text="⬅️ Orqaga", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def crm_students_keyboard(members: list[dict], prefix: str, back_callback: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for member in members:
        builder.button(text=member["student_name"], callback_data=f"{prefix}:{member['student_id']}")
    builder.button(text="⬅️ Orqaga", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def attendance_mode_keyboard(back_callback: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Keldi", callback_data="att_mode_arrived")
    builder.button(text="\U0001f3e0 Ketdi", callback_data="att_mode_left")
    builder.button(text="\U0001f4d6 Tarixni ko'rish", callback_data="att_mode_view")
    builder.button(text="⬅️ Orqaga", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def attendance_select_keyboard(
    members: list[dict], selected: set[int], toggle_prefix: str, confirm_callback: str, back_callback: str
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for member in members:
        mark = "✅" if member["student_id"] in selected else "⬜"
        builder.button(
            text=f"{mark} {member['student_name']}", callback_data=f"{toggle_prefix}:{member['student_id']}"
        )
    builder.button(text="✔️ Tasdiqlash", callback_data=confirm_callback)
    builder.button(text="⬅️ Orqaga", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def broadcast_prompt_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Bekor qilish", callback_data="bc_cancel")
    builder.adjust(1)
    return builder.as_markup()


def broadcast_confirm_keyboard(recipient_count: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=f"✅ Yuborish ({recipient_count} kishiga)", callback_data="bc_confirm_send")
    builder.button(text="❌ Bekor qilish", callback_data="bc_cancel")
    builder.adjust(1)
    return builder.as_markup()


def broadcast_role_keyboard(roles: list[Role]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="\U0001f310 Barcha xodimlar", callback_data="bc_workers_role:all")
    for role in roles:
        builder.button(text=role.name, callback_data=f"bc_workers_role:{role.id}")
    builder.button(text="❌ Bekor qilish", callback_data="bc_cancel")
    builder.adjust(1)
    return builder.as_markup()


def panel_choice_keyboard(show_admin: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if show_admin:
        builder.button(text="\U0001f6e0 Admin", callback_data="adm_menu")
    builder.adjust(1)
    return builder.as_markup()
