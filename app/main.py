"""Точка входа FastAPI-приложения СДО KMGE Edu."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db
from .routers import ai, analytics, auth, certificates, courses, learning, users
from .seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="MVP системы дистанционного обучения (аналог Moodle-СДО).",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(courses.router)
app.include_router(learning.router)
app.include_router(certificates.router)
app.include_router(ai.router)
app.include_router(analytics.router)


@app.get("/api/health", tags=["health"])
async def health():
    return {"status": "ok", "app": settings.app_name}
