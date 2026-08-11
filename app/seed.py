"""Наполнение БД начальными данными при первом запуске."""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models
from .config import settings
from .database import SessionLocal
from .security import hash_password

_DEMO_COURSES = [
    {
        "title": "Промышленная безопасность",
        "category": "Промбезопасность",
        "description": "Базовый курс по промышленной безопасности на опасных производственных объектах.",
        "pass_score": 80,
        "lessons": [
            (
                "Основные понятия",
                "Промышленная безопасность — состояние защищённости жизненно важных "
                "интересов личности и общества от аварий на опасных производственных "
                "объектах (ОПО) и последствий указанных аварий. К ОПО относятся объекты, "
                "на которых используются, хранятся или транспортируются опасные вещества.",
            ),
            (
                "Обязанности работников",
                "Работник обязан соблюдать требования промышленной безопасности, "
                "проходить обучение и аттестацию, немедленно сообщать руководителю об "
                "аварийных ситуациях, приостанавливать работу в случае угрозы жизни.",
            ),
            (
                "Действия при аварии",
                "При возникновении аварии необходимо оповестить окружающих, сообщить "
                "диспетчеру, покинуть опасную зону по плану эвакуации и оказать первую "
                "помощь пострадавшим.",
            ),
        ],
        "quiz": {
            "title": "Итоговый тест по промбезопасности",
            "questions": [
                (
                    "Что такое опасный производственный объект (ОПО)?",
                    [
                        ("Объект, где используются или хранятся опасные вещества", True),
                        ("Любое офисное здание", False),
                        ("Только атомная электростанция", False),
                        ("Склад канцтоваров", False),
                    ],
                ),
                (
                    "Что обязан сделать работник при угрозе жизни?",
                    [
                        ("Приостановить работу и сообщить руководителю", True),
                        ("Продолжать работу до конца смены", False),
                        ("Уйти домой без предупреждения", False),
                        ("Ничего не предпринимать", False),
                    ],
                ),
                (
                    "Первое действие при возникновении аварии?",
                    [
                        ("Оповестить окружающих и диспетчера", True),
                        ("Сделать фото для отчёта", False),
                        ("Дождаться конца рабочего дня", False),
                        ("Продолжить работу", False),
                    ],
                ),
            ],
        },
    },
    {
        "title": "Безопасность и охрана труда (БиОТ)",
        "category": "Охрана труда",
        "description": "Курс по безопасности и охране труда для сотрудников предприятия.",
        "pass_score": 80,
        "lessons": [
            (
                "Введение в охрану труда",
                "Охрана труда — система сохранения жизни и здоровья работников в процессе "
                "трудовой деятельности, включающая правовые, социально-экономические, "
                "организационно-технические, санитарно-гигиенические и иные мероприятия.",
            ),
            (
                "Средства индивидуальной защиты",
                "СИЗ — средства, используемые работником для предотвращения или уменьшения "
                "воздействия вредных и опасных производственных факторов: каски, очки, "
                "перчатки, спецодежда, респираторы. Применять СИЗ обязательно.",
            ),
            (
                "Первая помощь",
                "При несчастном случае необходимо устранить воздействие опасного фактора, "
                "оценить состояние пострадавшего, вызвать скорую помощь и оказать первую "
                "помощь до прибытия медиков.",
            ),
        ],
        "quiz": {
            "title": "Итоговый тест по охране труда",
            "questions": [
                (
                    "Что такое охрана труда?",
                    [
                        ("Система сохранения жизни и здоровья работников", True),
                        ("Система штрафов для сотрудников", False),
                        ("Правила пожарной сигнализации", False),
                        ("Расписание отпусков", False),
                    ],
                ),
                (
                    "Что относится к СИЗ?",
                    [
                        ("Каска, очки, перчатки, респиратор", True),
                        ("Ноутбук и телефон", False),
                        ("Служебный автомобиль", False),
                        ("Пропуск на работу", False),
                    ],
                ),
                (
                    "Что сделать первым при несчастном случае?",
                    [
                        ("Устранить воздействие опасного фактора", True),
                        ("Заполнить документы", False),
                        ("Уйти на перерыв", False),
                        ("Сообщить в бухгалтерию", False),
                    ],
                ),
            ],
        },
    },
]


async def seed() -> None:
    async with SessionLocal() as db:  # type: AsyncSession
        await _ensure_admin(db)
        await _ensure_demo_courses(db)


async def _ensure_admin(db: AsyncSession) -> None:
    count = await db.scalar(select(func.count(models.User.id)))
    if count and count > 0:
        return
    admin = models.User(
        email=settings.first_admin_email,
        full_name=settings.first_admin_name,
        hashed_password=hash_password(settings.first_admin_password),
        role=models.UserRole.admin,
    )
    db.add(admin)
    # Демо-студент
    db.add(
        models.User(
            email="student@kmge.kz",
            full_name="Иванов Иван Иванович",
            department="Цех №1",
            position="Оператор",
            hashed_password=hash_password("student123"),
            role=models.UserRole.student,
        )
    )
    await db.commit()


async def _ensure_demo_courses(db: AsyncSession) -> None:
    count = await db.scalar(select(func.count(models.Course.id)))
    if count and count > 0:
        return
    admin = await db.scalar(
        select(models.User).where(models.User.role == models.UserRole.admin)
    )
    for spec in _DEMO_COURSES:
        course = models.Course(
            title=spec["title"],
            category=spec["category"],
            description=spec["description"],
            pass_score=spec["pass_score"],
            certificate_enabled=True,
            is_published=True,
            created_by=admin.id if admin else None,
        )
        db.add(course)
        await db.flush()
        for i, (title, content) in enumerate(spec["lessons"]):
            db.add(models.Lesson(course_id=course.id, title=title, content=content, order=i))
        quiz = models.Quiz(course_id=course.id, title=spec["quiz"]["title"])
        db.add(quiz)
        await db.flush()
        for qi, (qtext, answers) in enumerate(spec["quiz"]["questions"]):
            question = models.Question(quiz_id=quiz.id, text=qtext, order=qi)
            db.add(question)
            await db.flush()
            for atext, correct in answers:
                db.add(
                    models.Answer(question_id=question.id, text=atext, is_correct=correct)
                )
    await db.commit()
