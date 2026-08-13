"""Фикстуры pytest: изолированная SQLite-БД и TestClient со стартовыми данными."""
import os

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_kmge.db")
os.environ.setdefault("ANTHROPIC_API_KEY", "")  # AI выключен в тестах


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    db_path = "test_kmge.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    with TestClient(app) as c:
        yield c
    if os.path.exists(db_path):
        os.remove(db_path)


def _token(client, email: str, password: str) -> str:
    r = client.post("/api/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def admin_headers(client):
    return {"Authorization": f"Bearer {_token(client, 'admin@kmge.kz', 'admin12345')}"}


@pytest.fixture(scope="session")
def student_headers(client):
    return {"Authorization": f"Bearer {_token(client, 'student@kmge.kz', 'student123')}"}