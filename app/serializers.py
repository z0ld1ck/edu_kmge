"""Вспомогательные функции сериализации моделей в схемы."""
from __future__ import annotations

from datetime import datetime, timezone

from . import models, schemas


def _is_overdue(enr: models.Enrollment) -> bool:
    if enr.due_date is None or enr.status == models.EnrollmentStatus.completed:
        return False
    due = enr.due_date
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    return due < datetime.now(timezone.utc)


def enrollment_out(enr: models.Enrollment) -> schemas.EnrollmentOut:
    return schemas.EnrollmentOut(
        id=enr.id,
        user_id=enr.user_id,
        course_id=enr.course_id,
        status=enr.status,
        progress=enr.progress,
        enrolled_at=enr.enrolled_at,
        completed_at=enr.completed_at,
        due_date=enr.due_date,
        is_mandatory=bool(enr.is_mandatory),
        assigned=enr.assigned_by_id is not None,
        is_overdue=_is_overdue(enr),
    )


def course_out(course: models.Course) -> schemas.CourseOut:
    return schemas.CourseOut(
        id=course.id,
        title=course.title,
        description=course.description,
        category=course.category,
        cover_url=course.cover_url,
        pass_score=course.pass_score,
        certificate_enabled=course.certificate_enabled,
        is_published=course.is_published,
        created_at=course.created_at,
        lessons_count=len(course.lessons),
        has_quiz=course.quiz is not None,
    )


def course_detail(course: models.Course) -> schemas.CourseDetail:
    base = course_out(course)
    return schemas.CourseDetail(
        **base.model_dump(),
        lessons=[schemas.LessonOut.model_validate(le) for le in course.lessons],
    )