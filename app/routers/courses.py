"""Курсы: CRUD, уроки, тест. Управление — admin/teacher."""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .. import models, schemas
from ..config import settings
from ..database import get_db
from ..deps import get_current_user, require_staff
from ..serializers import course_detail, course_out

router = APIRouter(prefix="/api/courses", tags=["courses"])

_MEDIA_LESSONS = Path(settings.media_root) / "lessons"
_MEDIA_COVERS = Path(settings.media_root) / "covers"
_COVER_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
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

    await db.delete(lesson)
    await db.commit()


@router.post("/{course_id}/lessons/reorder", response_model=schemas.CourseDetail)
async def reorder_lessons(
        course_id: int,
        data: schemas.LessonReorder,
        db: AsyncSession = Depends(get_db),
        _: models.User = Depends(require_staff),
):
    course = await _get_course(db, course_id)
    by_id = {l.id: l for l in course.lessons}
    unknown = [lid for lid in data.lesson_ids if lid not in by_id]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Уроки не найдены: {unknown}")
    for index, lid in enumerate(data.lesson_ids):
        by_id[lid].order = index
    await db.commit()
    course = await _get_course(db, course_id)
    return course_detail(course)


# ---------- Материалы урока ----------
def _material_url(lesson_id: int, filename: str) -> str:
    return f"/api/courses/materials/{lesson_id}/{filename}"


async def _get_lesson_or_404(db: AsyncSession, lesson_id: int) -> models.Lesson:
    lesson = await db.get(models.Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")
    return lesson


@router.post("/lessons/{lesson_id}/materials/link", response_model=schemas.LessonOut)
async def add_material_link(
        lesson_id: int,
        data: schemas.MaterialLinkCreate,
        db: AsyncSession = Depends(get_db),
        _: models.User = Depends(require_staff),
):
    """Добавить материал-ссылку на внешний ресурс."""
    lesson = await _get_lesson_or_404(db, lesson_id)
    material = {
        "id": uuid.uuid4().hex,
        "title": data.title or data.url,
        "url": data.url,
        "type": data.type or "link",
        "file": False,
    }
    lesson.materials = list(lesson.materials or []) + [material]
    await db.commit()
    await db.refresh(lesson)
    return lesson


@router.post("/lessons/{lesson_id}/materials/upload", response_model=schemas.LessonOut)
async def upload_material(
        lesson_id: int,
        title: str = Form(""),
        file: UploadFile = File(...),
        db: AsyncSession = Depends(get_db),
        _: models.User = Depends(require_staff),
):
    """Загрузить PDF-файл материала. Файл кладётся на диск, в БД — метаданные."""
    lesson = await _get_lesson_or_404(db, lesson_id)
    is_pdf = (file.content_type == "application/pdf") or (
            file.filename or ""
    ).lower().endswith(".pdf")
    if not is_pdf:
        raise HTTPException(status_code=400, detail="Разрешены только PDF-файлы")

    data = await file.read()
    limit = settings.max_upload_mb * 1024 * 1024
    if len(data) > limit:
        raise HTTPException(
            status_code=400,
            detail=f"Файл больше {settings.max_upload_mb} МБ",
        )

    dest_dir = _MEDIA_LESSONS / str(lesson_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}.pdf"
    (dest_dir / stored).write_bytes(data)

    material = {
        "id": uuid.uuid4().hex,
        "title": title.strip() or (file.filename or "Материал"),
        "url": _material_url(lesson_id, stored),
        "type": "pdf",
        "file": True,
    }
    lesson.materials = list(lesson.materials or []) + [material]
    await db.commit()
    await db.refresh(lesson)
    return lesson


@router.delete("/lessons/{lesson_id}/materials/{material_id}", response_model=schemas.LessonOut)
async def delete_material(
        lesson_id: int,
        material_id: str,
        db: AsyncSession = Depends(get_db),
        _: models.User = Depends(require_staff),
):
    """Удалить материал (и файл с диска, если это загруженный файл)."""
    lesson = await _get_lesson_or_404(db, lesson_id)
    materials = list(lesson.materials or [])
    kept: list[dict] = []
    removed: dict | None = None
    for m in materials:
        if m.get("id") == material_id:
            removed = m
        else:
            kept.append(m)
    if removed is None:
        raise HTTPException(status_code=404, detail="Материал не найден")
    if removed.get("file"):
        fname = removed.get("url", "").rsplit("/", 1)[-1]
        try:
            (_MEDIA_LESSONS / str(lesson_id) / fname).unlink(missing_ok=True)
        except Exception:
            pass
    lesson.materials = kept
    await db.commit()
    await db.refresh(lesson)
    return lesson


@router.get("/materials/{lesson_id}/{filename}")
async def get_material_file(
        lesson_id: int,
        filename: str,
        _: models.User = Depends(get_current_user),
):
    """Отдать PDF-файл (для встроенного просмотра через авторизованный запрос)."""
    safe = Path(filename).name  # защита от path traversal
    path = _MEDIA_LESSONS / str(lesson_id) / safe
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path, media_type="application/pdf", filename=safe)


# ---------- Обложка курса ----------
@router.post("/{course_id}/cover", response_model=schemas.CourseDetail)
async def upload_cover(
        course_id: int,
        file: UploadFile = File(...),
        db: AsyncSession = Depends(get_db),
        _: models.User = Depends(require_staff),
):
    """Загрузить картинку-обложку курса. Файл кладётся на диск, в cover_url —
    ссылка на раздачу."""
    course = await _get_course(db, course_id)
    ext = _COVER_EXT.get((file.content_type or "").lower())
    if ext is None:
        # Фолбэк по расширению: http-multipart часто шлёт octet-stream.
        name = (file.filename or "").lower()
        for e in (".jpeg", ".jpg", ".png", ".webp", ".gif"):
            if name.endswith(e):
                ext = ".jpg" if e == ".jpeg" else e
                break
    if ext is None:
        raise HTTPException(
            status_code=400, detail="Разрешены изображения JPG, PNG, WEBP, GIF"
        )
    data = await file.read()
    limit = settings.max_upload_mb * 1024 * 1024
    if len(data) > limit:
        raise HTTPException(
            status_code=400, detail=f"Файл больше {settings.max_upload_mb} МБ"
        )
    dest_dir = _MEDIA_COVERS / str(course_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    # чистим прежние файлы обложки этого курса
    for old in dest_dir.glob("*"):
        try:
            old.unlink()
        except OSError:
            pass
    stored = f"{uuid.uuid4().hex}{ext}"
    (dest_dir / stored).write_bytes(data)
    course.cover_url = f"/api/courses/cover/{course_id}/{stored}"
    await db.commit()
    course = await _get_course(db, course_id)
    return course_detail(course)


@router.get("/cover/{course_id}/{filename}")
async def get_cover_file(course_id: int, filename: str):
    """Отдать файл обложки (публично — используется в <img>)."""
    safe = Path(filename).name
    path = _MEDIA_COVERS / str(course_id) / safe
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path)


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
