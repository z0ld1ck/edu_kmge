"""Аналитика и отчёты (admin/teacher)."""
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models, schemas
from ..database import get_db
from ..deps import require_staff
from ..services import analytics

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview", response_model=schemas.OverviewStats)
async def overview(
    db: AsyncSession = Depends(get_db),
    _: models.User = Depends(require_staff),
):
    return await analytics.overview(db)


@router.get("/courses", response_model=list[schemas.CourseStat])
async def courses(
    db: AsyncSession = Depends(get_db),
    _: models.User = Depends(require_staff),
):
    return await analytics.course_stats(db)


@router.get("/users", response_model=list[schemas.UserProgressStat])
async def users(
    db: AsyncSession = Depends(get_db),
    _: models.User = Depends(require_staff),
):
    return await analytics.user_stats(db)


@router.get("/export/users.xlsx")
async def export_users(
    db: AsyncSession = Depends(get_db),
    _: models.User = Depends(require_staff),
):
    data = await analytics.export_users_xlsx(db)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="users-progress.xlsx"'},
    )
