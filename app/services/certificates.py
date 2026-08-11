"""Генерация PDF-сертификатов о прохождении курса."""
from __future__ import annotations

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_FONT = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"

# Попытка подключить шрифт с поддержкой кириллицы.
for _path in (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
):
    try:
        pdfmetrics.registerFont(TTFont("Cyr", _path))
        _bold = _path.replace("Sans.ttf", "Sans-Bold.ttf").replace(
            "Regular", "Bold"
        )
        try:
            pdfmetrics.registerFont(TTFont("Cyr-Bold", _bold))
            _FONT_BOLD = "Cyr-Bold"
        except Exception:
            _FONT_BOLD = "Cyr"
        _FONT = "Cyr"
        break
    except Exception:
        continue


def generate_certificate_pdf(
    *,
    user_name: str,
    course_title: str,
    category: str,
    serial_number: str,
    score: float,
    issued_at: datetime,
) -> bytes:
    buffer = io.BytesIO()
    page = landscape(A4)
    width, height = page
    c = canvas.Canvas(buffer, pagesize=page)

    # Рамка
    c.setStrokeColor(colors.HexColor("#0B6E4F"))
    c.setLineWidth(6)
    c.rect(12 * mm, 12 * mm, width - 24 * mm, height - 24 * mm)
    c.setLineWidth(1)
    c.setStrokeColor(colors.HexColor("#1F8A70"))
    c.rect(16 * mm, 16 * mm, width - 32 * mm, height - 32 * mm)

    center = width / 2

    c.setFillColor(colors.HexColor("#0B6E4F"))
    c.setFont(_FONT_BOLD, 30)
    c.drawCentredString(center, height - 45 * mm, "СЕРТИФИКАТ")

    c.setFont(_FONT, 14)
    c.setFillColor(colors.HexColor("#333333"))
    c.drawCentredString(center, height - 58 * mm, "о прохождении обучения")

    c.setFont(_FONT, 13)
    c.drawCentredString(center, height - 78 * mm, "Настоящим удостоверяется, что")

    c.setFont(_FONT_BOLD, 24)
    c.setFillColor(colors.HexColor("#111111"))
    c.drawCentredString(center, height - 92 * mm, user_name)

    c.setFont(_FONT, 13)
    c.setFillColor(colors.HexColor("#333333"))
    c.drawCentredString(center, height - 108 * mm, "успешно завершил(а) курс")

    c.setFont(_FONT_BOLD, 17)
    c.setFillColor(colors.HexColor("#0B6E4F"))
    c.drawCentredString(center, height - 120 * mm, f"«{course_title}»")

    c.setFont(_FONT, 12)
    c.setFillColor(colors.HexColor("#333333"))
    c.drawCentredString(
        center, height - 132 * mm, f"Направление: {category}   •   Результат: {score:.0f}%"
    )

    # Нижняя строка: номер и дата
    c.setFont(_FONT, 10)
    c.setFillColor(colors.HexColor("#666666"))
    c.drawString(30 * mm, 26 * mm, f"№ {serial_number}")
    c.drawRightString(width - 30 * mm, 26 * mm, f"Дата: {issued_at.strftime('%d.%m.%Y')}")

    c.drawCentredString(center, 20 * mm, "KMGE Edu — Система дистанционного обучения")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()
