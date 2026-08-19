"""Настройка асинхронного подключения к БД (SQLAlchemy 2.0)."""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """Создать таблицы (для MVP — без миграций Alembic)."""
    # Импорт моделей нужен, чтобы они зарегистрировались в metadata.
    from . import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Лёгкая авто-миграция для существующих БД (dev, без Alembic):
        # добавляем новые колонки назначений, если их ещё нет.
        for ddl in (
            "ALTER TABLE enrollments ADD COLUMN due_date TIMESTAMP",
            "ALTER TABLE enrollments ADD COLUMN is_mandatory BOOLEAN",
            "ALTER TABLE enrollments ADD COLUMN assigned_by_id INTEGER",
            "ALTER TABLE lessons ADD COLUMN materials JSON",
        ):
            try:
                await conn.exec_driver_sql(ddl)
            except Exception:
                pass  # колонка уже существует