"""End-to-end smoke-тест на SQLite (без Postgres)."""
import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./smoke.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

# Убрать старую БД
if os.path.exists("smoke.db"):
    os.remove("smoke.db")


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


with TestClient(app) as client:
    # health
    assert client.get("/api/health").json()["status"] == "ok"

    # admin login
    r = client.post(
        "/api/auth/login",
        data={"username": "admin@kmge.kz", "password": "admin12345"},
    )
    assert r.status_code == 200, r.text
    admin_t = r.json()["access_token"]

    # список курсов (демо промбез + БиОТ)
    r = client.get("/api/courses", headers=bearer(admin_t))
    assert r.status_code == 200, r.text
    courses = r.json()
    assert len(courses) == 2, courses
    print("Курсы:", [c["title"] for c in courses])
    assert all(c["lessons_count"] == 3 and c["has_quiz"] for c in courses)

    # регистрация нового студента
    r = client.post(
        "/api/auth/register",
        json={"email": "test@kmge.kz", "full_name": "Тест Тестов", "password": "pass123"},
    )
    assert r.status_code == 201, r.text

    r = client.post(
        "/api/auth/login", data={"username": "test@kmge.kz", "password": "pass123"}
    )
    stud_t = r.json()["access_token"]

    course_id = courses[0]["id"]

    # запись на курс
    r = client.post(f"/api/courses/{course_id}/enroll", headers=bearer(stud_t))
    assert r.status_code == 201, r.text

    # детали курса + уроки
    detail = client.get(f"/api/courses/{course_id}", headers=bearer(stud_t)).json()
    lessons = detail["lessons"]
    assert len(lessons) == 3

    # пройти все уроки
    for le in lessons:
        r = client.post(f"/api/lessons/{le['id']}/complete", headers=bearer(stud_t))
        assert r.status_code == 200, r.text
    enr = r.json()
    print("Прогресс после уроков:", enr["progress"], enr["status"])
    assert enr["progress"] == 100.0

    # получить тест (без флагов правильности)
    quiz = client.get(f"/api/courses/{course_id}/quiz", headers=bearer(stud_t)).json()
    assert "questions" in quiz and len(quiz["questions"]) == 3
    for q in quiz["questions"]:
        for a in q["answers"]:
            assert "is_correct" not in a  # флаг скрыт от студента

    # сдать тест правильно (первый ответ у демо — правильный)
    answers = [
        {"question_id": q["id"], "answer_id": q["answers"][0]["id"]}
        for q in quiz["questions"]
    ]
    r = client.post(
        f"/api/courses/{course_id}/quiz/submit",
        json={"answers": answers},
        headers=bearer(stud_t),
    )
    assert r.status_code == 200, r.text
    result = r.json()
    print("Результат теста:", result)
    assert result["passed"] is True
    assert result["score"] == 100.0
    assert result["certificate_id"] is not None

    # сертификаты студента
    certs = client.get("/api/certificates", headers=bearer(stud_t)).json()
    assert len(certs) == 1
    cert_id = certs[0]["id"]

    # скачать PDF
    r = client.get(f"/api/certificates/{cert_id}/download", headers=bearer(stud_t))
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    print("PDF-сертификат сгенерирован, размер:", len(r.content), "байт")

    # аналитика (admin)
    ov = client.get("/api/analytics/overview", headers=bearer(admin_t)).json()
    print("Аналитика overview:", ov)
    assert ov["total_courses"] == 2
    assert ov["certificates_issued"] == 1

    # экспорт xlsx
    r = client.get("/api/analytics/export/users.xlsx", headers=bearer(admin_t))
    assert r.status_code == 200
    assert len(r.content) > 0

    # RBAC: студент не может к аналитике
    r = client.get("/api/analytics/overview", headers=bearer(stud_t))
    assert r.status_code == 403

    # AI status (ключ не задан)
    st = client.get("/api/ai/status", headers=bearer(admin_t)).json()
    assert st["enabled"] is False

    # создание курса персоналом
    r = client.post(
        "/api/courses",
        json={"title": "Пожарная безопасность", "category": "Пожбез"},
        headers=bearer(admin_t),
    )
    assert r.status_code == 201, r.text
    print("Создан курс:", r.json()["title"])

print("\n✅ ВСЕ SMOKE-ТЕСТЫ ПРОЙДЕНЫ")
os.remove("smoke.db")
