from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from models import AuditAccount, Employee, FineTemplate, ParentLink, Role

# ── Doimiy pastki menyu tugma matnlari (komandalar bilan bir xil ishlaydi) ──────

BTN_WORKERS = "\U0001f465 Xodimlar"
BTN_ROLES = "\U0001f3ad Rollar"
BTN_AUDIT_ACCOUNTS = "\U0001f511 Audit akkauntlari"
BTN_TEMPLATES = "\U0001f4dd Shablonlar"
BTN_REPORTS = "\U0001f4ca Hisobotlar"
BTN_BROADCAST = "\U0001f4e2 Xabar yuborish"
BTN_LINK_PARENT = "\U0001f517 Ota-onani biriktirish"
BTN_ATTENDANCE = "\U0001f4cb Davomat"
BTN_PAYMENT = "\U0001f4b0 To'lov holati"
BTN_SETTINGS = "\U00002699 Sozlamalar"

BTN_FINE_GIVE = "\U0001f9fe Shtraf berish"
BTN_FINE_REPORT = "\U0001f4ca Hisobot"
BTN_MY_TEMPLATES = "\U0001f5c2 Mening shablonlarim"

BTN_MY_FINES = "\U0001f4b5 Mening shtraflarim"

BTN_MY_CHILD = "\U0001f476 Farzandim"
BTN_SCHEDULE = "\U0001f4c5 Jadval"

BTN_REQUEST_CHILD = "\U0001f517 Farzand biriktirish"


def admin_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_WORKERS), KeyboardButton(text=BTN_ROLES)],
            [KeyboardButton(text=BTN_AUDIT_ACCOUNTS), KeyboardButton(text=BTN_TEMPLATES)],
            [KeyboardButton(text=BTN_REPORTS), KeyboardButton(text=BTN_BROADCAST)],
            [KeyboardButton(text=BTN_LINK_PARENT), KeyboardButton(text=BTN_ATTENDANCE)],
            [KeyboardButton(text=BTN_PAYMENT), KeyboardButton(text=BTN_SETTINGS)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def audit_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_FINE_GIVE), KeyboardButton(text=BTN_FINE_REPORT)],
            [KeyboardButton(text=BTN_MY_TEMPLATES)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def worker_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_MY_FINES)]],
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
    builder.button(text="\U0001f9fe Shtraflar hisoboti", callback_data="report_start")
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
    builder.button(text="\U0001f5bc Shtrafda rasm majburiymi", callback_data="toggle_fine_photo")
    builder.button(text="➕ Yangi admin qo'shish", callback_data="new_admin_start")
    builder.button(text="➖ Adminlikdan olish", callback_data="remove_admin_start")
    builder.adjust(1)
    return builder.as_markup()


def children_keyboard(links: list[ParentLink]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for link in links:
        builder.button(text=link.student_name, callback_data=f"child_detail:{link.id}")
    builder.adjust(1)
    return builder.as_markup()


def fine_totals_keyboard(
    employees: list[Employee], totals: dict[int, tuple[int, int]], back_callback: str
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for employee in employees:
        amount, _count = totals.get(employee.id, (0, 0))
        amount_str = f"{amount:,}".replace(",", " ")
        builder.button(
            text=f"\U0001f464 {employee.full_name} — {amount_str} so'm",
            callback_data=f"report_emp:{employee.id}",
        )
    builder.button(text="⬅️ Orqaga", callback_data=back_callback)
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


def audit_accounts_keyboard(
    accounts: list[AuditAccount], back_callback: str | None = None
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for account in accounts:
        status = "✅ Faol" if account.is_active else "\U0001f6ab Nofaol"
        name = account.employee.full_name if account.employee else "?"
        builder.button(text=f"{name} ({account.login}) — {status}", callback_data=f"audit_detail:{account.id}")
    builder.button(text="➕ Yangi audit yaratish", callback_data="new_audit")
    if back_callback:
        builder.button(text="⬅️ Orqaga", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def audit_account_detail_keyboard(account: AuditAccount, back_callback: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    toggle_text = "\U0001f6ab Nofaol qilish" if account.is_active else "✅ Faol qilish"
    builder.button(text=toggle_text, callback_data=f"toggle_audit:{account.id}")
    builder.button(text="\U0001f504 Parolni yangilash", callback_data=f"reset_audit_pwd:{account.id}")
    builder.button(text="⬅️ Orqaga", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def fine_templates_keyboard(
    templates: list[FineTemplate], prefix: str, back_callback: str | None = None
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for template in templates:
        builder.button(text=template.short_name, callback_data=f"{prefix}:{template.id}")
    if back_callback:
        builder.button(text="⬅️ Orqaga", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def admin_templates_keyboard(
    templates: list[FineTemplate], back_callback: str | None = None
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for template in templates:
        status = "✅" if template.is_active else "\U0001f6ab"
        shared = "\U0001f465" if template.shared_with_audit else ""
        builder.button(
            text=f"{template.short_name} {status}{shared}", callback_data=f"template_detail:{template.id}"
        )
    builder.button(text="➕ Yangi shablon qo'shish", callback_data="new_template")
    if back_callback:
        builder.button(text="⬅️ Orqaga", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def template_detail_keyboard(template: FineTemplate, back_callback: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Matnni tahrirlash", callback_data=f"edit_template:{template.id}")
    active_text = "\U0001f6ab Nofaol qilish" if template.is_active else "✅ Faol qilish"
    builder.button(text=active_text, callback_data=f"toggle_template:{template.id}")
    share_text = "\U0001f465 Auditdan yashirish" if template.shared_with_audit else "\U0001f465 Auditga ko'rsatish"
    builder.button(text=share_text, callback_data=f"toggle_template_share:{template.id}")
    builder.button(text="⬅️ Orqaga", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def audit_templates_manage_keyboard(
    templates: list[FineTemplate], back_callback: str | None = None
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for template in templates:
        status = "✅ Faol" if template.is_active else "\U0001f6ab Nofaol"
        builder.button(
            text=f"{template.short_name} — {status}", callback_data=f"toggle_audit_template:{template.id}"
        )
    builder.button(text="➕ Yangi shablon qo'shish", callback_data="new_audit_template")
    if back_callback:
        builder.button(text="⬅️ Orqaga", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def audit_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="\U0001f9fe Shtraf berish", callback_data="fine_start")
    builder.button(text="\U0001f4ca Hisobot", callback_data="report_start")
    builder.button(text="\U0001f5c2 Mening shablonlarim", callback_data="audit_templates_menu")
    builder.button(text="⬅️ Orqaga", callback_data="panel_root")
    builder.adjust(1)
    return builder.as_markup()


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="\U0001f465 Xodimlar", callback_data="adm_workers")
    builder.button(text="\U0001f3ad Rollar", callback_data="adm_roles")
    builder.button(text="\U0001f511 Audit akkauntlari", callback_data="adm_audits")
    builder.button(text="\U0001f4dd Shablonlar", callback_data="adm_templates")
    builder.button(text="\U0001f4ca Hisobot", callback_data="adm_report")
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


def parent_link_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash", callback_data=f"apprlink:{request_id}")
    builder.button(text="❌ Rad etish", callback_data=f"rejlink:{request_id}")
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


def photo_prompt_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="\U000023ed Rasm shart emas", callback_data="fine_skip_photo")
    builder.adjust(1)
    return builder.as_markup()


def panel_choice_keyboard(show_admin: bool, show_audit: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if show_admin:
        builder.button(text="\U0001f6e0 Admin", callback_data="adm_menu")
    if show_audit:
        builder.button(text="\U0001f575 Audit", callback_data="panel_audit")
    builder.adjust(1)
    return builder.as_markup()
