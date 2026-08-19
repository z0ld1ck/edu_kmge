"""Назначение курсов сотрудникам/подразделениям с дедлайнами (админ/преподаватель)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models, schemas
from ..database import get_db
from ..deps import require_staff
from ..serializers import _is_overdue

router = APIRouter(prefix="/api/admin/assignments", tags=["assignments"])


@router.post("", response_model=schemas.AssignmentResult, status_code=201)
async def create_assignment(
    data: schemas.AssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current: models.User = Depends(require_staff),
):
    course = await db.get(models.Course, data.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")

    # Собираем целевых пользователей: явный список + все активные из подразделения.
    target_ids: set[int] = set(data.user_ids)
    if data.department:
        rows = await db.execute(
            select(models.User.id).where(
                models.User.department == data.department,
                models.User.is_active.is_(True),
            )
        )
        target_ids.update(r[0] for r in rows.all())

    if not target_ids:
        raise HTTPException(
            status_code=400, detail="Не выбраны сотрудники или подразделение"
        )

    assigned = 0
    for uid in target_ids:
        user = await db.get(models.User, uid)
        if user is None:
            continue
        enr = await db.scalar(
            select(models.Enrollment).where(
                models.Enrollment.user_id == uid,
                models.Enrollment.course_id == data.course_id,
            )
        )
        if enr is None:
            enr = models.Enrollment(user_id=uid, course_id=data.course_id)
            db.add(enr)
        enr.due_date = data.due_date
        enr.is_mandatory = data.is_mandatory
        enr.assigned_by_id = current.id
        assigned += 1

    await db.commit()
    return schemas.AssignmentResult(assigned=assigned)


@router.get("", response_model=list[schemas.AssignmentRow])
async def list_assignments(
    course_id: int | None = Query(None),
    department: str | None = Query(None),
    status: str | None = Query(None, description="overdue | pending | completed"),
    db: AsyncSession = Depends(get_db),
    current: models.User = Depends(require_staff),
):
    stmt = (
        select(models.Enrollment, models.User, models.Course)
        .join(models.User, models.User.id == models.Enrollment.user_id)
        .join(models.Course, models.Course.id == models.Enrollment.course_id)
        .where(models.Enrollment.assigned_by_id.is_not(None))
    )
    if course_id is not None:
        stmt = stmt.where(models.Enrollment.course_id == course_id)
    if department:
        stmt = stmt.where(models.User.department == department)
    stmt = stmt.order_by(models.Enrollment.due_date.is_(None), models.Enrollment.due_date)

    rows = await db.execute(stmt)
    out: list[schemas.AssignmentRow] = []
    for enr, user, course in rows.all():
        overdue = _is_overdue(enr)
        if status == "overdue" and not overdue:
            continue
        if status == "completed" and enr.status != models.EnrollmentStatus.completed:
            continue
        if status == "pending" and (
            overdue or enr.status == models.EnrollmentStatus.completed
        ):
            continue
        out.append(
            schemas.AssignmentRow(
                enrollment_id=enr.id,
                user_id=user.id,
                user_name=user.full_name,
                department=user.department,
                course_id=course.id,
                course_title=course.title,
                status=enr.status,
                progress=enr.progress,
                due_date=enr.due_date,
                is_mandatory=bool(enr.is_mandatory),
                is_overdue=overdue,
            )
        )
    return out


@router.delete("/{enrollment_id}", status_code=204)
async def remove_assignment(
    enrollment_id: int,
    db: AsyncSession = Depends(get_db),
    current: models.User = Depends(require_staff),
):
    enr = await db.get(models.Enrollment, enrollment_id)
    if enr is None or enr.assigned_by_id is None:
        raise HTTPException(status_code=404, detail="Назначение не найдено")
    # Снимаем назначение, но саму запись на курс (прогресс) сохраняем.
    enr.due_date = None
    enr.is_mandatory = False
    enr.assigned_by_id = None
    await db.commit()
