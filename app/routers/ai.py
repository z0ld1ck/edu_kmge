"""AI-ассистент (Claude): чат по курсу и авто-генерация теста."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .. import models, schemas
from ..config import settings
from ..database import get_db
from ..deps import get_current_user, require_staff
from ..services import ai

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/status")
async def ai_status(_: models.User = Depends(get_current_user)):
    return {"enabled": bool(settings.anthropic_api_key), "model": settings.anthropic_model}


async def _course_material(db: AsyncSession, course_id: int) -> models.Course:
    course = await db.scalar(
        select(models.Course)
        .options(selectinload(models.Course.lessons))
        .where(models.Course.id == course_id)
    )
    if not course:
        raise HTTPException(status_code=404, detail="Курс не найден")
    return course


def _join_material(course: models.Course) -> str:
    parts = [course.description]
    for lesson in course.lessons:
        parts.append(f"# {lesson.title}\n{lesson.content}")
    return "\n\n".join(p for p in parts if p)


@router.post("/chat", response_model=schemas.AIChatResponse)
async def chat(
    data: schemas.AIChatRequest,
    db: AsyncSession = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    course = await _course_material(db, data.course_id)
    try:
        reply = ai.chat(course.title, _join_material(course), data.message, data.history)
    except ai.AIUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return schemas.AIChatResponse(reply=reply)


@router.post("/generate-quiz")
async def generate_quiz(
    data: schemas.AIGenerateQuizRequest,
    db: AsyncSession = Depends(get_db),
    _: models.User = Depends(require_staff),
):
    """Возвращает черновик вопросов (не сохраняет). Персонал редактирует и
    сохраняет через PUT /api/courses/{id}/quiz."""
    course = await _course_material(db, data.course_id)
    material = _join_material(course)
    if len(material) < 40:
        raise HTTPException(status_code=400, detail="Недостаточно материала для генерации")
    try:
        questions = ai.generate_quiz(course.title, material, data.num_questions)
    except ai.AIUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"title": "Итоговый тест", "time_limit_minutes": 0, "questions": questions}
