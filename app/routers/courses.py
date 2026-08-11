"""Курсы: CRUD, уроки, тест. Управление — admin/teacher."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user, require_staff
from ..serializers import course_detail, course_out

router = APIRouter(prefix="/api/courses", tags=["courses"])

_LOAD = (selectinload(models.Course.lessons), selectinload(models.Course.quiz))


async def _get_course(db: AsyncSession, course_id: int) -> models.Course:
    stmt = select(models.Course).options(*_LOAD).where(models.Course.id == course_id)
    course = await db.scalar(stmt)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")
    return course


@router.get("", response_model=list[schemas.CourseOut])
async def list_courses(
    q: str | None = None,
    category: str | None = None,
    published_only: bool = True,
    db: AsyncSession = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    stmt = select(models.Course).options(*_LOAD).order_by(models.Course.created_at.desc())
    # Студент видит только опубликованные; персонал — все.
    if current.role == models.UserRole.student or published_only:
        stmt = stmt.where(models.Course.is_published.is_(True))
    if category:
        stmt = stmt.where(models.Course.category == category)
    if q:
        stmt = stmt.where(models.Course.title.ilike(f"%{q}%"))
    result = await db.execute(stmt)
    return [course_out(c) for c in result.scalars().all()]


@router.get("/categories", response_model=list[str])
async def categories(
    db: AsyncSession = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    result = await db.execute(select(models.Course.category).distinct())
    return sorted({row for row in result.scalars().all() if row})


@router.get("/{course_id}", response_model=schemas.CourseDetail)
async def get_course(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    course = await _get_course(db, course_id)
    return course_detail(course)


@router.post("", response_model=schemas.CourseDetail, status_code=201)
async def create_course(
    data: schemas.CourseCreate,
    db: AsyncSession = Depends(get_db),
    staff: models.User = Depends(require_staff),
):
    course = models.Course(**data.model_dump(), created_by=staff.id)
    db.add(course)
    await db.commit()
    course = await _get_course(db, course.id)
    return course_detail(course)


@router.patch("/{course_id}", response_model=schemas.CourseDetail)
async def update_course(
    course_id: int,
    data: schemas.CourseUpdate,
    db: AsyncSession = Depends(get_db),
    _: models.User = Depends(require_staff),
):
    course = await _get_course(db, course_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(course, field, value)
    await db.commit()
    course = await _get_course(db, course_id)
    return course_detail(course)


@router.delete("/{course_id}", status_code=204)
async def delete_course(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    _: models.User = Depends(require_staff),
):
    course = await db.get(models.Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")
    await db.delete(course)
    await db.commit()


# ---------- Уроки ----------
@router.post("/{course_id}/lessons", response_model=schemas.LessonOut, status_code=201)
async def add_lesson(
    course_id: int,
    data: schemas.LessonCreate,
    db: AsyncSession = Depends(get_db),
    _: models.User = Depends(require_staff),
):
    course = await db.get(models.Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")
    lesson = models.Lesson(course_id=course_id, **data.model_dump())
    db.add(lesson)
    await db.commit()
    await db.refresh(lesson)
    return lesson


@router.patch("/lessons/{lesson_id}", response_model=schemas.LessonOut)
async def update_lesson(
    lesson_id: int,
    data: schemas.LessonUpdate,
    db: AsyncSession = Depends(get_db),
    _: models.User = Depends(require_staff),
):
    lesson = await db.get(models.Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(lesson, field, value)
    await db.commit()
    await db.refresh(lesson)
    return lesson


@router.delete("/lessons/{lesson_id}", status_code=204)
async def delete_lesson(
    lesson_id: int,
    db: AsyncSession = Depends(get_db),
    _: models.User = Depends(require_staff),
):
    lesson = await db.get(models.Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")
    await db.delete(lesson)
    await db.commit()


# ---------- Тест ----------
@router.put("/{course_id}/quiz", response_model=schemas.QuizOut)
async def set_quiz(
    course_id: int,
    data: schemas.QuizCreate,
    db: AsyncSession = Depends(get_db),
    _: models.User = Depends(require_staff),
):
    """Полностью заменяет тест курса (idempotent)."""
    course = await _get_course(db, course_id)
    if course.quiz is not None:
        await db.delete(course.quiz)
        await db.flush()
    quiz = models.Quiz(
        course_id=course_id, title=data.title, time_limit_minutes=data.time_limit_minutes
    )
    db.add(quiz)
    await db.flush()
    for q in data.questions:
        question = models.Question(quiz_id=quiz.id, text=q.text, order=q.order)
        db.add(question)
        await db.flush()
        for a in q.answers:
            db.add(models.Answer(question_id=question.id, text=a.text, is_correct=a.is_correct))
    await db.commit()
    return await _quiz_out(db, quiz.id)


@router.get("/{course_id}/quiz", response_model=schemas.QuizOut)
async def get_quiz(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    quiz = await db.scalar(
        select(models.Quiz)
        .options(selectinload(models.Quiz.questions).selectinload(models.Question.answers))
        .where(models.Quiz.course_id == course_id)
    )
    if not quiz:
        raise HTTPException(status_code=404, detail="Тест для курса не создан")
    return _serialize_quiz(quiz)


async def _quiz_out(db: AsyncSession, quiz_id: int) -> schemas.QuizOut:
    quiz = await db.scalar(
        select(models.Quiz)
        .options(selectinload(models.Quiz.questions).selectinload(models.Question.answers))
        .where(models.Quiz.id == quiz_id)
    )
    return _serialize_quiz(quiz)


def _serialize_quiz(quiz: models.Quiz) -> schemas.QuizOut:
    return schemas.QuizOut(
        id=quiz.id,
        course_id=quiz.course_id,
        title=quiz.title,
        time_limit_minutes=quiz.time_limit_minutes,
        questions=[
            schemas.QuestionOut(
                id=q.id,
                text=q.text,
                order=q.order,
                answers=[schemas.AnswerOut(id=a.id, text=a.text) for a in q.answers],
            )
            for q in quiz.questions
        ],
    )
