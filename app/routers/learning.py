"""Учебный процесс студента: запись на курс, прохождение уроков, сдача теста."""
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user
from ..serializers import course_out

router = APIRouter(prefix="/api", tags=["learning"])


async def _get_enrollment(
    db: AsyncSession, user_id: int, course_id: int
) -> models.Enrollment | None:
    return await db.scalar(
        select(models.Enrollment)
        .options(selectinload(models.Enrollment.lesson_progress))
        .where(
            models.Enrollment.user_id == user_id,
            models.Enrollment.course_id == course_id,
        )
    )


async def _recompute_progress(db: AsyncSession, enrollment: models.Enrollment) -> None:
    """Пересчёт прогресса по доле завершённых уроков."""
    from sqlalchemy import func

    total_lessons = await db.scalar(
        select(func.count(models.Lesson.id)).where(
            models.Lesson.course_id == enrollment.course_id
        )
    )
    done = await db.scalar(
        select(func.count(models.LessonProgress.id)).where(
            models.LessonProgress.enrollment_id == enrollment.id,
            models.LessonProgress.completed.is_(True),
        )
    )
    total_lessons = total_lessons or 0
    done = done or 0
    if total_lessons:
        enrollment.progress = round(done / total_lessons * 100, 1)
    if enrollment.status == models.EnrollmentStatus.enrolled and done > 0:
        enrollment.status = models.EnrollmentStatus.in_progress


@router.post("/courses/{course_id}/enroll", response_model=schemas.EnrollmentOut, status_code=201)
async def enroll(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    course = await db.get(models.Course, course_id)
    if not course or not course.is_published:
        raise HTTPException(status_code=404, detail="Курс не найден или не опубликован")
    existing = await _get_enrollment(db, current.id, course_id)
    if existing:
        return existing
    enrollment = models.Enrollment(user_id=current.id, course_id=course_id)
    db.add(enrollment)
    await db.commit()
    await db.refresh(enrollment)
    return enrollment


@router.get("/my/courses", response_model=list[schemas.MyCourseOut])
async def my_courses(
    db: AsyncSession = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    result = await db.execute(
        select(models.Enrollment)
        .options(
            selectinload(models.Enrollment.course).selectinload(models.Course.lessons),
            selectinload(models.Enrollment.course).selectinload(models.Course.quiz),
        )
        .where(models.Enrollment.user_id == current.id)
        .order_by(models.Enrollment.enrolled_at.desc())
    )
    out: list[schemas.MyCourseOut] = []
    for enr in result.scalars().all():
        out.append(
            schemas.MyCourseOut(
                course=course_out(enr.course),
                enrollment=schemas.EnrollmentOut.model_validate(enr),
            )
        )
    return out

@router.get("/my/attempts", response_model=list[schemas.AttemptOut])
async def my_attempts(
    db: AsyncSession = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    """История попыток прохождения тестов текущим пользователем."""
    rows = await db.execute(
        select(models.QuizAttempt, models.Course.id, models.Course.title)
        .join(models.Quiz, models.Quiz.id == models.QuizAttempt.quiz_id)
        .join(models.Course, models.Course.id == models.Quiz.course_id)
        .where(models.QuizAttempt.user_id == current.id)
        .order_by(models.QuizAttempt.created_at.desc())
    )
    out: list[schemas.AttemptOut] = []
    for attempt, course_id, course_title in rows.all():
        out.append(
            schemas.AttemptOut(
                id=attempt.id,
                quiz_id=attempt.quiz_id,
                course_id=course_id,
                course_title=course_title,
                score=attempt.score,
                passed=attempt.passed,
                created_at=attempt.created_at,
            )
        )
    return out



@router.get("/courses/{course_id}/progress", response_model=list[int])
async def completed_lessons(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    """Список ID завершённых уроков в рамках курса."""
    enrollment = await _get_enrollment(db, current.id, course_id)
    if not enrollment:
        return []
    return [lp.lesson_id for lp in enrollment.lesson_progress if lp.completed]


@router.post("/lessons/{lesson_id}/complete", response_model=schemas.EnrollmentOut)
async def complete_lesson(
    lesson_id: int,
    db: AsyncSession = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    lesson = await db.get(models.Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")
    enrollment = await _get_enrollment(db, current.id, lesson.course_id)
    if not enrollment:
        raise HTTPException(status_code=400, detail="Вы не записаны на курс")

    lp = await db.scalar(
        select(models.LessonProgress).where(
            models.LessonProgress.enrollment_id == enrollment.id,
            models.LessonProgress.lesson_id == lesson_id,
        )
    )
    if lp is None:
        lp = models.LessonProgress(
            enrollment_id=enrollment.id,
            lesson_id=lesson_id,
            completed=True,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(lp)
    else:
        lp.completed = True
        lp.completed_at = datetime.now(timezone.utc)
    await db.flush()

    await _recompute_progress(db, enrollment)

    # Если у курса нет теста, а все уроки пройдены — курс завершён.
    from sqlalchemy import func

    has_quiz = await db.scalar(
        select(func.count(models.Quiz.id)).where(models.Quiz.course_id == lesson.course_id)
    )
    if not has_quiz and enrollment.progress >= 100:
        enrollment.status = models.EnrollmentStatus.completed
        enrollment.completed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(enrollment)
    return enrollment


@router.post("/courses/{course_id}/quiz/submit", response_model=schemas.QuizResult)
async def submit_quiz(
    course_id: int,
    submission: schemas.QuizSubmission,
    db: AsyncSession = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    course = await db.get(models.Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")
    quiz = await db.scalar(
        select(models.Quiz)
        .options(selectinload(models.Quiz.questions).selectinload(models.Question.answers))
        .where(models.Quiz.course_id == course_id)
    )
    if not quiz:
        raise HTTPException(status_code=404, detail="Тест не найден")
    enrollment = await _get_enrollment(db, current.id, course_id)
    if not enrollment:
        raise HTTPException(status_code=400, detail="Вы не записаны на курс")

    correct_by_q: dict[int, int] = {}
    for q in quiz.questions:
        for a in q.answers:
            if a.is_correct:
                correct_by_q[q.id] = a.id
                break

    chosen = {s.question_id: s.answer_id for s in submission.answers}
    total = len(quiz.questions)
    correct = sum(
        1 for qid, aid in correct_by_q.items() if chosen.get(qid) == aid
    )
    score = round(correct / total * 100, 1) if total else 0.0
    passed = score >= course.pass_score

    db.add(
        models.QuizAttempt(
            quiz_id=quiz.id, user_id=current.id, score=score, passed=passed
        )
    )

    certificate_id: int | None = None
    if passed:
        enrollment.status = models.EnrollmentStatus.completed
        enrollment.progress = 100.0
        enrollment.completed_at = datetime.now(timezone.utc)
        if course.certificate_enabled:
            existing = await db.scalar(
                select(models.Certificate).where(
                    models.Certificate.user_id == current.id,
                    models.Certificate.course_id == course_id,
                )
            )
            if existing:
                existing.score = max(existing.score, score)
                certificate_id = existing.id
            else:
                cert = models.Certificate(
                    user_id=current.id,
                    course_id=course_id,
                    serial_number=f"KMGE-{course_id}-{secrets.token_hex(4).upper()}",
                    score=score,
                )
                db.add(cert)
                await db.flush()
                certificate_id = cert.id

    await db.commit()
    return schemas.QuizResult(
        score=score, passed=passed, correct=correct, total=total, certificate_id=certificate_id
    )
