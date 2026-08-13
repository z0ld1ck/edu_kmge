"""Функциональные тесты API СДО (SQLite, весь основной флоу)."""


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_login_wrong_password(client):
    r = client.post(
        "/api/auth/login", data={"username": "admin@kmge.kz", "password": "wrong"}
    )
    assert r.status_code == 401


def test_seed_courses(client, admin_headers):
    courses = client.get("/api/courses", headers=admin_headers).json()
    assert len(courses) == 2
    assert all(c["lessons_count"] == 3 and c["has_quiz"] for c in courses)
    titles = {c["title"] for c in courses}
    assert "Промышленная безопасность" in titles


def test_register_and_login(client):
    r = client.post(
        "/api/auth/register",
        json={"email": "u1@kmge.kz", "full_name": "Пользователь Один", "password": "pass123"},
    )
    assert r.status_code == 201
    r = client.post("/api/auth/login", data={"username": "u1@kmge.kz", "password": "pass123"})
    assert r.status_code == 200


def test_full_learning_flow_issues_certificate(client):
    # Отдельный студент, чтобы не мешать другим тестам.
    client.post(
        "/api/auth/register",
        json={"email": "flow@kmge.kz", "full_name": "Флоу Тестов", "password": "pass123"},
    )
    tok = client.post(
        "/api/auth/login", data={"username": "flow@kmge.kz", "password": "pass123"}
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}

    courses = client.get("/api/courses", headers=h).json()
    course_id = courses[0]["id"]

    assert client.post(f"/api/courses/{course_id}/enroll", headers=h).status_code == 201

    detail = client.get(f"/api/courses/{course_id}", headers=h).json()
    for lesson in detail["lessons"]:
        assert client.post(f"/api/lessons/{lesson['id']}/complete", headers=h).status_code == 200

    quiz = client.get(f"/api/courses/{course_id}/quiz", headers=h).json()
    # Флаг правильности скрыт от студента.
    for q in quiz["questions"]:
        for a in q["answers"]:
            assert "is_correct" not in a

    # Демо-тесты: правильный ответ — первый вариант.
    answers = [
        {"question_id": q["id"], "answer_id": q["answers"][0]["id"]}
        for q in quiz["questions"]
    ]
    result = client.post(
        f"/api/courses/{course_id}/quiz/submit", json={"answers": answers}, headers=h
    ).json()
    assert result["passed"] is True
    assert result["score"] == 100.0
    assert result["certificate_id"] is not None

    certs = client.get("/api/certificates", headers=h).json()
    assert len(certs) == 1
    cert = certs[0]

    # Скачивание PDF.
    r = client.get(f"/api/certificates/{cert['id']}/download", headers=h)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"

    # Публичная проверка по номеру — без авторизации.
    v = client.get(f"/api/certificates/verify/{cert['serial_number']}").json()
    assert v["valid"] is True
    assert v["user_name"] == "Флоу Тестов"

    # История попыток.
    attempts = client.get("/api/my/attempts", headers=h).json()
    assert len(attempts) == 1
    assert attempts[0]["passed"] is True
    assert attempts[0]["course_id"] == course_id


def test_certificate_verify_invalid(client):
    v = client.get("/api/certificates/verify/NONEXISTENT-0000").json()
    assert v["valid"] is False


def test_self_profile_and_password(client):
    client.post(
        "/api/auth/register",
        json={"email": "prof@kmge.kz", "full_name": "Профиль Тестов", "password": "pass123"},
    )
    tok = client.post(
        "/api/auth/login", data={"username": "prof@kmge.kz", "password": "pass123"}
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}

    r = client.patch("/api/auth/me", json={"department": "Цех №2"}, headers=h)
    assert r.status_code == 200
    assert r.json()["department"] == "Цех №2"

    # Неверный старый пароль.
    r = client.post(
        "/api/auth/change-password",
        json={"old_password": "nope", "new_password": "newpass1"},
        headers=h,
    )
    assert r.status_code == 400

    # Корректная смена пароля и вход с новым.
    r = client.post(
        "/api/auth/change-password",
        json={"old_password": "pass123", "new_password": "newpass1"},
        headers=h,
    )
    assert r.status_code == 204
    assert (
        client.post(
            "/api/auth/login", data={"username": "prof@kmge.kz", "password": "newpass1"}
        ).status_code
        == 200
    )


def test_rbac_student_cannot_access_analytics(client, student_headers):
    assert client.get("/api/analytics/overview", headers=student_headers).status_code == 403


def test_admin_analytics_overview(client, admin_headers):
    ov = client.get("/api/analytics/overview", headers=admin_headers).json()
    assert ov["total_courses"] == 2
    assert ov["certificates_issued"] >= 1


def test_ai_disabled(client, admin_headers):
    assert client.get("/api/ai/status", headers=admin_headers).json()["enabled"] is False


def test_staff_creates_course_and_pagination(client, admin_headers):
    r = client.post(
        "/api/courses",
        json={"title": "Пожарная безопасность", "category": "Пожбез"},
        headers=admin_headers,
    )
    assert r.status_code == 201

    users = client.get("/api/users?limit=2&offset=0", headers=admin_headers).json()
    assert len(users) <= 2
