"""Агрегация статистики для дашборда и экспорт в Excel."""
from __future__ import annotations

import io

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models


async def overview(db: AsyncSession) -> dict:
    total_users = await db.scalar(select(func.count(models.User.id)))
    total_courses = await db.scalar(select(func.count(models.Course.id)))
    total_enr = await db.scalar(select(func.count(models.Enrollment.id)))
    completed = await db.scalar(
        select(func.count(models.Enrollment.id)).where(
            models.Enrollment.status == models.EnrollmentStatus.completed
        )
    )
    certs = await db.scalar(select(func.count(models.Certificate.id)))
    total_enr = total_enr or 0
    completed = completed or 0
    rate = (completed / total_enr * 100) if total_enr else 0.0
    return {
        "total_users": total_users or 0,
        "total_courses": total_courses or 0,
        "total_enrollments": total_enr,
        "completed_enrollments": completed,
        "certificates_issued": certs or 0,
        "completion_rate": round(rate, 1),
    }


async def course_stats(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(models.Course))
    courses = result.scalars().all()
    stats: list[dict] = []
    for course in courses:
        enrolled = await db.scalar(
            select(func.count(models.Enrollment.id)).where(
                models.Enrollment.course_id == course.id
            )
        )
        completed = await db.scalar(
            select(func.count(models.Enrollment.id)).where(
                models.Enrollment.course_id == course.id,
                models.Enrollment.status == models.EnrollmentStatus.completed,
            )
        )
        avg_progress = await db.scalar(
            select(func.avg(models.Enrollment.progress)).where(
                models.Enrollment.course_id == course.id
            )
        )
        avg_score = None
        if course.quiz is not None:
            avg_score = await db.scalar(
                select(func.avg(models.QuizAttempt.score)).where(
                    models.QuizAttempt.quiz_id == course.quiz.id
                )
            )
        stats.append(
            {
                "course_id": course.id,
                "title": course.title,
                "category": course.category,
                "enrolled": enrolled or 0,
                "completed": completed or 0,
                "avg_progress": round(avg_progress or 0.0, 1),
                "avg_score": round(avg_score, 1) if avg_score is not None else None,
            }
        )
    return stats


async def user_stats(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(models.User).where(models.User.role == models.UserRole.student)
    )
    users = result.scalars().all()
    stats: list[dict] = []
    for user in users:
        enrolled = await db.scalar(
            select(func.count(models.Enrollment.id)).where(
                models.Enrollment.user_id == user.id
            )
        )
        completed = await db.scalar(
            select(func.count(models.Enrollment.id)).where(
                models.Enrollment.user_id == user.id,
                models.Enrollment.status == models.EnrollmentStatus.completed,
            )
        )
        avg_progress = await db.scalar(
            select(func.avg(models.Enrollment.progress)).where(
                models.Enrollment.user_id == user.id
            )
        )
        stats.append(
            {
                "user_id": user.id,
                "full_name": user.full_name,
                "department": user.department,
                "enrolled": enrolled or 0,
                "completed": completed or 0,
                "avg_progress": round(avg_progress or 0.0, 1),
            }
        )
    return stats


async def export_users_xlsx(db: AsyncSession) -> bytes:
    from openpyxl import Workbook

    rows = await user_stats(db)
    wb = Workbook()
    ws = wb.active
    ws.title = "Прогресс сотрудников"
    headers = ["ID", "ФИО", "Подразделение", "Записан на курсов", "Завершено", "Средний прогресс, %"]
    ws.append(headers)
    for r in rows:
        ws.append(
            [
                r["user_id"],
                r["full_name"],
                r["department"] or "",
                r["enrolled"],
                r["completed"],
                r["avg_progress"],
            ]
        )
    for col in ws.columns:
        width = max((len(str(cell.value)) for cell in col if cell.value is not None), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(width + 4, 50)
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.read()
