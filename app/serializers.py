"""Вспомогательные функции сериализации моделей в схемы."""
from __future__ import annotations

from . import models, schemas


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
