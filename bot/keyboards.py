from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from models import AuditAccount, Employee, FineTemplate, Role


def employees_keyboard(
    employees: list[Employee], prefix: str, back_callback: str | None = None
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for employee in employees:
        role_part = f" ({employee.role.name})" if employee.role else ""
        builder.button(text=f"{employee.full_name}{role_part}", callback_data=f"{prefix}:{employee.id}")
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
        builder.button(text=template.text, callback_data=f"{prefix}:{template.id}")
    if back_callback:
        builder.button(text="⬅️ Orqaga", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def fine_templates_manage_keyboard(
    templates: list[FineTemplate], back_callback: str | None = None
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for template in templates:
        status = "✅ Faol" if template.is_active else "\U0001f6ab Nofaol"
        builder.button(text=f"{template.text} — {status}", callback_data=f"toggle_template:{template.id}")
    builder.button(text="➕ Yangi shablon qo'shish", callback_data="new_template")
    if back_callback:
        builder.button(text="⬅️ Orqaga", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def audit_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="\U0001f9fe Shtraf berish", callback_data="fine_start")
    builder.button(text="\U0001f4ca Hisobot", callback_data="report_start")
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
    builder.button(text="⬅️ Orqaga", callback_data="panel_root")
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
