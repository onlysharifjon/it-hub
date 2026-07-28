from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from database import async_session
from keyboards import panel_choice_keyboard
from models import Employee
from utils import get_employee, safe_edit_text

router = Router(name="panel")


async def _panel_view(session, telegram_id: int) -> tuple[Employee | None, bool]:
    employee = await get_employee(session, telegram_id)
    if employee is None:
        return None, False
    return employee, employee.is_admin


@router.message(F.text == "/panel")
async def panel_command(message: Message) -> None:
    async with async_session() as session:
        employee, show_admin = await _panel_view(session, message.from_user.id)
    if employee is None:
        await message.answer("Avval botga /start bosing.")
        return
    if not show_admin:
        await message.answer("Sizda panel uchun ruxsat yo'q.")
        return
    await message.answer("Panelni tanlang:", reply_markup=panel_choice_keyboard(show_admin))


@router.callback_query(F.data == "panel_root")
async def panel_root(callback: CallbackQuery) -> None:
    async with async_session() as session:
        employee, show_admin = await _panel_view(session, callback.from_user.id)
    if employee is None or not show_admin:
        await callback.answer("Sizda panel uchun ruxsat yo'q.", show_alert=True)
        return
    await safe_edit_text(
        callback.message, "Panelni tanlang:", reply_markup=panel_choice_keyboard(show_admin)
    )
    await callback.answer()
