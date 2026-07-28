from datetime import timedelta

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

import crm_client
from database import async_session
from keyboards import children_keyboard
from models import Attendance, ParentLink
from utils import format_new_links_notice, get_employee, sync_parent_links_from_crm

router = Router(name="profile")


async def _student_detail_text(
    session, crm_student_id: int, student_name: str, crm_group_id: int, group_name: str
) -> str:
    visits_result = await session.execute(
        select(Attendance)
        .where(Attendance.crm_student_id == crm_student_id)
        .order_by(Attendance.created_at.desc())
        .limit(10)
    )
    visits = list(visits_result.scalars().all())

    try:
        detail = await crm_client.get_group_detail(crm_group_id)
        schedule_text = detail.get("schedule") or "jadval belgilanmagan"
    except crm_client.CRMError:
        schedule_text = "hozircha olib bo'lmadi"

    lines = [
        f"\U0001f465 {student_name} — {group_name}",
        f"\U0001f4c5 Jadval: {schedule_text}",
        "",
        "Kelish/ketish tarixi:",
    ]
    if not visits:
        lines.append("Hozircha qayd etilmagan.")
    else:
        for visit in reversed(visits):
            icon = "✅ Keldi" if visit.kind == "arrived" else "\U0001f3e0 Ketdi"
            local_time = visit.created_at + timedelta(hours=5)
            lines.append(f"  {icon} — {local_time:%d.%m.%Y %H:%M}")
    return "\n".join(lines)


async def _child_detail_text(session, link: ParentLink) -> str:
    return await _student_detail_text(
        session, link.crm_student_id, link.student_name, link.crm_group_id, link.group_name
    )


@router.message(F.text == "/farzandim")
async def my_children_start(message: Message) -> None:
    async with async_session() as session:
        employee = await get_employee(session, message.from_user.id)
        if employee is None:
            await message.answer("Avval botga /start bosing.")
            return
        result = await session.execute(
            select(ParentLink).where(ParentLink.employee_id == employee.id)
        )
        links = result.scalars().all()
        if not links:
            newly_linked = await sync_parent_links_from_crm(session, employee)
            if newly_linked:
                await message.answer(format_new_links_notice(newly_linked))
                result = await session.execute(
                    select(ParentLink).where(ParentLink.employee_id == employee.id)
                )
                links = result.scalars().all()
        if not links:
            await message.answer("Sizga hech qanday farzand biriktirilmagan. Admin bilan bog'laning.")
            return
        if len(links) == 1:
            text = await _child_detail_text(session, links[0])
            await message.answer(text)
            return

    await message.answer("Qaysi farzandingiz haqida ma'lumot olmoqchisiz?", reply_markup=children_keyboard(links))


@router.callback_query(F.data.startswith("child_detail:"))
async def child_detail(callback: CallbackQuery) -> None:
    link_id = int(callback.data.split(":")[1])
    async with async_session() as session:
        employee = await get_employee(session, callback.from_user.id)
        link = await session.get(ParentLink, link_id)
        if employee is None or link is None or link.employee_id != employee.id:
            await callback.answer("Ruxsat yo'q.", show_alert=True)
            return
        text = await _child_detail_text(session, link)
    await callback.message.answer(text)
    await callback.answer()


@router.message(F.text == "/jadval")
async def my_children_schedule(message: Message) -> None:
    async with async_session() as session:
        employee = await get_employee(session, message.from_user.id)
        if employee is None:
            await message.answer("Avval botga /start bosing.")
            return
        result = await session.execute(
            select(ParentLink).where(ParentLink.employee_id == employee.id)
        )
        links = result.scalars().all()
        if not links:
            newly_linked = await sync_parent_links_from_crm(session, employee)
            if newly_linked:
                await message.answer(format_new_links_notice(newly_linked))
                result = await session.execute(
                    select(ParentLink).where(ParentLink.employee_id == employee.id)
                )
                links = result.scalars().all()

    if not links:
        await message.answer("Sizga hech qanday farzand biriktirilmagan. Admin bilan bog'laning.")
        return

    lines = []
    for link in links:
        try:
            detail = await crm_client.get_group_detail(link.crm_group_id)
            schedule_text = detail.get("schedule") or "jadval belgilanmagan"
        except crm_client.CRMError:
            schedule_text = "hozircha olib bo'lmadi"
        lines.append(f"\U0001f4c5 {link.student_name} — {link.group_name}\nJadval: {schedule_text}")
    await message.answer("\n\n".join(lines))
