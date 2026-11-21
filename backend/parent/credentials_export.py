"""Ota-ona login/parollarini Excel yoki PDF faylga chiqarish (CRM: ommaviy yaratishdan keyin).

Parollar bazada faqat bcrypt hash ko'rinishida saqlanadi — bu modul faqat hunter brauzerdan yuborgan,
hozirgina yaratilgan qiymatlarni faylga aylantiradi. Hech narsa saqlanmaydi va logga yozilmaydi.
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Iterable, List, Sequence

COLUMNS = ("№", "Ota-ona", "Farzand(lar)", "Login (telefon)", "Parol")
TITLE = "Minar Academy — ota-onalar ilovasi uchun login va parollar"
NOTE = ("Ilovaga kirish: login — telefon raqam, parol — jadvaldagi qiymat. "
        "Kirgandan keyin parolni o'zingiz almashtirishingiz tavsiya etiladi.")


def _rows(items: Iterable) -> List[Sequence[str]]:
    return [(str(i), r.full_name, r.children or "", r.username, r.password)
            for i, r in enumerate(items, start=1)]


def to_xlsx(items: Sequence, generated_at: datetime) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    wb = Workbook()
    ws = wb.active
    ws.title = "Login-parollar"
    ws.append([TITLE])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([f"Sana: {generated_at:%d.%m.%Y %H:%M}   ·   Jami: {len(items)} ta"])
    ws.append([])
    ws.append(list(COLUMNS))
    thin = Side(style="thin", color="D0D5DD")
    for cell in ws[4]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="4F46E5")
        cell.alignment = Alignment(vertical="center")
    for row in _rows(items):
        ws.append(list(row))
    for r in ws.iter_rows(min_row=4, max_row=ws.max_row):
        for cell in r:
            cell.border = Border(top=thin, bottom=thin, left=thin, right=thin)
    # Login/parol matn sifatida — Excel telefon raqamni songa aylantirib yubormasin
    for r in ws.iter_rows(min_row=5, min_col=4, max_col=5):
        for cell in r:
            cell.number_format = "@"
            cell.font = Font(name="Consolas", size=11)
    for col, width in zip("ABCDE", (5, 28, 34, 18, 20)):
        ws.column_dimensions[col].width = width
    ws.append([])
    ws.append([NOTE])
    ws.freeze_panes = "A5"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def to_pdf(items: Sequence, generated_at: datetime) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    from .engagement import _RECEIPT_FONT, _receipt_font   # DejaVuSans: o'zbek lotin + kirill

    _receipt_font()
    font = _RECEIPT_FONT
    title = ParagraphStyle("t", fontName=font, fontSize=14, leading=18, spaceAfter=2)
    small = ParagraphStyle("s", fontName=font, fontSize=9, leading=12, textColor=colors.HexColor("#475467"))
    cell = ParagraphStyle("c", fontName=font, fontSize=10, leading=13)
    mono = ParagraphStyle("m", fontName=font, fontSize=11, leading=14)

    def p(text: str, style=cell) -> Paragraph:
        esc = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return Paragraph(esc, style)

    data = [[p(c) for c in COLUMNS]]
    for no, parent, children, login, pwd in _rows(items):
        data.append([p(no), p(parent), p(children), p(login, mono), p(pwd, mono)])

    table = Table(data, colWidths=[12 * mm, 62 * mm, 78 * mm, 48 * mm, 50 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F46E5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D5DD")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FB")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    # Sarlavha qatori oq rangda bo'lishi uchun Paragraph rangini ham almashtiramiz
    for c in data[0]:
        c.style = ParagraphStyle("h", parent=cell, textColor=colors.white)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm, title="Ota-onalar login va parollari")
    doc.build([
        p(TITLE, title),
        p(f"Sana: {generated_at:%d.%m.%Y %H:%M}   ·   Jami: {len(items)} ta", small),
        Spacer(1, 6 * mm),
        table,
        Spacer(1, 5 * mm),
        p(NOTE, small),
    ])
    return buf.getvalue()
