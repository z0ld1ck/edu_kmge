"""Сертификаты: список и скачивание PDF."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user
from ..services.certificates import generate_certificate_pdf

router = APIRouter(prefix="/api/certificates", tags=["certificates"])


@router.get("", response_model=list[schemas.CertificateOut])
async def my_certificates(
    db: AsyncSession = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    result = await db.execute(
        select(models.Certificate)
        .options(selectinload(models.Certificate.course))
        .where(models.Certificate.user_id == current.id)
        .order_by(models.Certificate.issued_at.desc())
    )
    out = []
    for cert in result.scalars().all():
        item = schemas.CertificateOut.model_validate(cert)
        item.course_title = cert.course.title if cert.course else None
        item.user_name = current.full_name
        out.append(item)
    return out


@router.get("/{cert_id}/download")
async def download_certificate(
    cert_id: int,
    db: AsyncSession = Depends(get_db),
    current: models.User = Depends(get_current_user),
):
    cert = await db.scalar(
        select(models.Certificate)
        .options(
            selectinload(models.Certificate.course),
            selectinload(models.Certificate.user),
        )
        .where(models.Certificate.id == cert_id)
    )
    if not cert:
        raise HTTPException(status_code=404, detail="Сертификат не найден")
    # Скачивать может владелец или персонал.
    if cert.user_id != current.id and current.role == models.UserRole.student:
        raise HTTPException(status_code=403, detail="Нет доступа к сертификату")

    pdf = generate_certificate_pdf(
        user_name=cert.user.full_name,
        course_title=cert.course.title,
        category=cert.course.category,
        serial_number=cert.serial_number,
        score=cert.score,
        issued_at=cert.issued_at,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="certificate-{cert.serial_number}.pdf"'
        },
    )
