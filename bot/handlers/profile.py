from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import func, select

from database import async_session
from models import Fine
from utils import get_employee

router = Router(name="profile")


@router.message(F.text == "/shtraflarim")
async def my_fines(message: Message) -> None:
    async with async_session() as session:
        employee = await get_employee(session, message.from_user.id)
        if employee is None:
            await message.answer("Avval botga /start bosing.")
            return
        result = await session.execute(
            select(Fine).where(Fine.employee_id == employee.id).order_by(Fine.created_at.desc())
        )
        fines = result.scalars().all()
        total_result = await session.execute(
            select(func.coalesce(func.sum(Fine.amount), 0)).where(Fine.employee_id == employee.id)
        )
        total = total_result.scalar_one()

    if not fines:
        await message.answer("Sizda shtraflar yo'q.")
        return

    total_str = f"{total:,}".replace(",", " ")
    lines = [f"\U0001f4ca Sizning shtraflaringiz — jami: {total_str} so'm", ""]
    for fine in fines:
        amount_str = f"{fine.amount:,}".replace(",", " ")
        lines.append(f"• {fine.created_at:%d.%m.%Y %H:%M} — {amount_str} so'm ({fine.reason})")
    await message.answer("\n".join(lines))
