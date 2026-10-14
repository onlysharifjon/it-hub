"""Parent engagement data assembled from real CRM records."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from sqlalchemy.orm import Session

from .. import models, tz
from . import schemas, service


def absence_read(row: models.ParentAbsenceExplanation) -> schemas.AbsenceExplanationRead:
    attendance = row.attendance
    return schemas.AbsenceExplanationRead(
        id=row.id, child_id=row.student_id, lesson_date=attendance.lesson_date,
        group_name=attendance.group.name if attendance.group else "",
        reason=row.reason, note=row.note or "", status=row.status,
        staff_note=row.staff_note, created_at=row.created_at, reviewed_at=row.reviewed_at,
    )


def question_read(row: models.ParentTeacherQuestion) -> schemas.TeacherQuestionRead:
    return schemas.TeacherQuestionRead(
        id=row.id, child_id=row.student_id, subject=row.subject, body=row.body,
        status=row.status, created_at=row.created_at,
        replies=[schemas.TeacherReplyRead(
            id=reply.id, body=reply.body,
            author_name=service._user_name(reply.staff) or "O'qituvchi",
            created_at=reply.created_at,
        ) for reply in row.replies],
    )


def weekly_summary(db: Session, student: models.Student, week_start: date | None = None) -> schemas.WeeklySummaryRead:
    today = tz.today()
    monday = week_start or (today - timedelta(days=today.weekday()))
    sunday = monday + timedelta(days=6)
    observed_end = min(sunday, today)
    attendance = db.query(models.Attendance).filter(
        models.Attendance.student_id == student.id,
        models.Attendance.lesson_date >= monday,
        models.Attendance.lesson_date <= observed_end,
        models.Attendance.is_present.isnot(None),
    ).all()
    attended = sum(1 for row in attendance if row.is_present)
    # Denominator reflects lessons actually recorded by staff. Planned future lessons
    # are not treated as absences or completed lessons.
    scheduled = len(attendance)

    active_ids = {m.group_id for m in service.active_memberships(student)}
    homework = db.query(models.Homework).filter(
        models.Homework.group_id.in_(active_ids or {0}),
        models.Homework.lesson_date >= monday,
        models.Homework.lesson_date <= observed_end,
    ).all()
    submissions = {s.homework_id: s for s in db.query(models.HomeworkSubmission).filter(
        models.HomeworkSubmission.student_id == student.id,
        models.HomeworkSubmission.homework_id.in_([h.id for h in homework] or [0]),
    ).all()}
    completed = sum(1 for h in homework if submissions.get(h.id) and
                    submissions[h.id].status in ("submitted", "graded", "done"))
    grades = db.query(models.Grade).filter(
        models.Grade.student_id == student.id,
        models.Grade.exam_date >= monday,
        models.Grade.exam_date <= observed_end,
        models.Grade.max_score > 0,
    ).all()
    average = round(sum(max(0, min(g.score, g.max_score)) / g.max_score for g in grades) / len(grades) * 100) if grades else None
    recommendation = db.query(models.ParentWeeklyRecommendation).filter(
        models.ParentWeeklyRecommendation.student_id == student.id,
        models.ParentWeeklyRecommendation.week_start == monday,
    ).first()

    highlights: list[str] = []
    needs_attention: list[str] = []
    if scheduled:
        highlights.append(f"{attended}/{scheduled} darsda qatnashdi.")
        if attended < scheduled:
            needs_attention.append(f"{scheduled - attended} ta dars qoldirildi. Sababini tekshiring.")
    if homework:
        highlights.append(f"{completed}/{len(homework)} ta uy vazifasi bajarildi.")
        if completed < len(homework):
            needs_attention.append(f"{len(homework) - completed} ta uy vazifasi kutilmoqda.")
    if average is not None:
        highlights.append(f"Baholarning o'rtacha natijasi {average}%.")
        low = [g.subject for g in grades if g.score / g.max_score < 0.6]
        if low:
            needs_attention.append(f"{low[0]} mavzusini o'qituvchi bilan takrorlang.")
    if not highlights:
        highlights.append("Bu hafta bo'yicha hali ma'lumot kiritilmagan.")
    return schemas.WeeklySummaryRead(
        week_start=monday, week_end=sunday, attended_lessons=attended,
        scheduled_lessons=scheduled, homework_completed=completed,
        homework_total=len(homework), average_grade=average,
        highlights=highlights, needs_attention=needs_attention,
        teacher_recommendation=recommendation.text if recommendation else None,
    )


_RECEIPT_FONT = "Minar-DejaVu"
_RECEIPT_FONT_PATH = Path(__file__).resolve().parent.parent / "static" / "fonts" / "DejaVuSans.ttf"


def _receipt_font() -> None:
    if _RECEIPT_FONT not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(_RECEIPT_FONT, str(_RECEIPT_FONT_PATH)))


def verified_receipt_pdf(invoice: models.ParentInvoice) -> bytes:
    """Unicode one-page confirmation; caller enforces ownership and provider status."""
    _receipt_font()
    amount = int(Decimal(str(invoice.amount)))
    transaction = next((t for t in invoice.transactions if t.state == "performed"), None)
    paid_at = tz.to_local(invoice.paid_at or invoice.created_at)
    rows = [
        ("Invoys", f"#{invoice.id}"),
        ("Provayder", invoice.provider.upper()),
        ("Tranzaksiya ID", transaction.provider_txn_id if transaction else "—"),
        ("To‘lov sanasi", paid_at.strftime("%d.%m.%Y %H:%M") + " (Toshkent)"),
        ("Talaba", invoice.student.full_name if invoice.student else str(invoice.student_id)),
        ("Guruh", invoice.group.name if invoice.group else str(invoice.group_id)),
        ("Summa", f"{amount:,}".replace(",", " ") + " so‘m"),
        ("Holat", "Provayder tomonidan tasdiqlangan"),
    ]
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, pageCompression=1)
    pdf.setTitle(f"Minar Academy to‘lov tasdiqnomasi #{invoice.id}")
    pdf.setAuthor("Minar Academy")
    width, height = A4
    pdf.setFillColor(colors.HexColor("#9C3D0A"))
    pdf.rect(0, height - 124, width, 124, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont(_RECEIPT_FONT, 21)
    pdf.drawString(46, height - 65, "MINAR ACADEMY")
    pdf.setFont(_RECEIPT_FONT, 12)
    pdf.drawString(46, height - 94, "To‘lov tasdiqnomasi")
    pdf.setFillColor(colors.HexColor("#263238"))
    y = height - 165
    for label, value in rows:
        pdf.setFont(_RECEIPT_FONT, 9)
        pdf.setFillColor(colors.HexColor("#6B7280"))
        pdf.drawString(46, y, label)
        pdf.setFont(_RECEIPT_FONT, 10)
        pdf.setFillColor(colors.HexColor("#263238"))
        # Names can be long; wrap without replacing Cyrillic/Uzbek glyphs.
        words, lines, line = str(value).split(), [], ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if pdfmetrics.stringWidth(candidate, _RECEIPT_FONT, 10) > 315 and line:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
        for index, text in enumerate(lines[:3]):
            pdf.drawString(200, y - index * 16, text)
        y -= max(39, len(lines[:3]) * 16 + 18)
        pdf.setStrokeColor(colors.HexColor("#ECEFF1"))
        pdf.line(46, y + 17, width - 46, y + 17)
    pdf.setFont(_RECEIPT_FONT, 9)
    pdf.setFillColor(colors.HexColor("#6B7280"))
    pdf.drawString(46, 86, "Bu tasdiqnoma fiskal yoki soliq cheki emas.")
    pdf.drawString(46, 68, "To‘lov holati Payme/Click/Uzum tasdig‘i asosida ko‘rsatilgan.")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
