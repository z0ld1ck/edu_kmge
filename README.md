# KMGE Edu — Backend (FastAPI)

API системы дистанционного обучения. Python 3.11+, FastAPI, SQLAlchemy 2.0 (async).

## Запуск (локально)

```bash
python -m venv .venv
# Windows:  py -3.11 -m venv .venv  &&  .\.venv\Scripts\Activate.ps1
source .venv/bin/activate
pip install -r requirements.txt

# Быстрый старт на SQLite (без Postgres):
export DATABASE_URL="sqlite+aiosqlite:///./edu.db"
uvicorn app.main:app --reload
```

Swagger — http://localhost:8000/docs. Демо-вход: `admin@kmge.kz` / `admin12345`,
`student@kmge.kz` / `student123`. При первом старте создаются демо-курсы
(«Промбезопасность», «БиОТ») и таблицы (`init_db` → `create_all`).

## Миграции (Alembic)

Для продакшена схема управляется Alembic (URL берётся из `DATABASE_URL`):

```bash
alembic upgrade head          # применить миграции
alembic revision --autogenerate -m "описание"   # новая миграция после правки models.py
alembic downgrade -1          # откатить последнюю
```

> `create_all` в `lifespan` удобен для dev/SQLite и idempotent. Для Postgres
> в проде используйте `alembic upgrade head`.

## Тесты

```bash
pytest -q
```
Тесты гоняются на временной SQLite-БД, покрывают весь флоу: регистрация,
курсы, уроки, тест, выдача и проверка сертификата, история попыток, профиль,
смена пароля, RBAC.

## Переменные окружения

См. `.env.example`. Ключевые:

| Переменная | Назначение |
|------------|-----------|
| `DATABASE_URL` | строка подключения (`postgresql+asyncpg://…` или `sqlite+aiosqlite://…`) |
| `SECRET_KEY` | секрет для подписи JWT |
| `CORS_ORIGINS` | домены фронтенда через запятую или `*` |
| `ANTHROPIC_API_KEY` | ключ Claude; пусто → AI-функции отдают 503 |
| `FIRST_ADMIN_EMAIL` / `FIRST_ADMIN_PASSWORD` | первичный админ |

## Структура

```
app/
├── main.py            точка входа, роутеры, CORS, lifespan
├── config.py          настройки (pydantic-settings)
├── database.py        async engine + сессии
├── models.py          ORM-модели
├── schemas.py         Pydantic-схемы
├── security.py        bcrypt + JWT
├── deps.py            текущий пользователь, RBAC
├── serializers.py     сериализация курсов
├── seed.py            демо-данные
├── routers/           auth, users, courses, learning, certificates, ai, analytics
└── services/          certificates (PDF), ai (Claude), analytics (Excel)
migrations/            Alembic
tests/                 pytest
```

## Обзор эндпоинтов

- `POST /api/auth/register` · `/login` · `GET/PATCH /api/auth/me` · `/change-password`
- `GET/POST/PATCH/DELETE /api/courses…` — курсы, уроки, тест
- `POST /api/courses/{id}/enroll`, `POST /api/lessons/{id}/complete`,
  `POST /api/courses/{id}/quiz/submit`, `GET /api/my/courses`, `GET /api/my/attempts`
- `GET /api/certificates`, `/{id}/download`, `GET /api/certificates/verify/{serial}` (публично)
- `POST /api/ai/chat` · `/generate-quiz` · `GET /api/ai/status`
- `GET /api/analytics/overview` · `/courses` · `/users` · `/export/users.xlsx`
