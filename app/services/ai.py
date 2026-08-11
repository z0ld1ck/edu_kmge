"""AI-ассистент на базе Claude (Anthropic).

Две функции:
  * chat  — помощник по материалам курса (Q&A);
  * generate_quiz — авто-генерация вопросов теста из текста лекций.

Если ключ Anthropic не задан — обе функции бросают AIUnavailable,
роутер превращает это в HTTP 503.
"""
from __future__ import annotations

import json

from ..config import settings


class AIUnavailable(RuntimeError):
    pass


def _client():
    if not settings.anthropic_api_key:
        raise AIUnavailable("AI-ассистент не настроен: не задан ANTHROPIC_API_KEY")
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise AIUnavailable("Пакет anthropic не установлен") from exc
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def chat(course_title: str, course_material: str, message: str, history: list[dict]) -> str:
    client = _client()
    system = (
        "Ты — обучающий ассистент СДО (система дистанционного обучения) "
        "для сотрудников. Отвечай кратко, по делу, на русском языке, опираясь "
        "на материалы курса. Если ответа в материалах нет — честно скажи об этом "
        "и дай общий безопасный совет.\n\n"
        f"Курс: {course_title}\n\n"
        f"Материалы курса:\n{course_material[:12000]}"
    )
    messages: list[dict] = []
    for h in history[-8:]:
        role = h.get("role")
        content = h.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})

    resp = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        system=system,
        messages=messages,
    )
    return "".join(block.text for block in resp.content if block.type == "text").strip()


def generate_quiz(course_title: str, course_material: str, num_questions: int) -> list[dict]:
    """Возвращает список вопросов в формате QuestionCreate-совместимых dict."""
    client = _client()
    system = (
        "Ты генерируешь тестовые вопросы для проверки знаний по курсу. "
        "Верни СТРОГО JSON-массив без пояснений. Формат каждого элемента:\n"
        '{"text": "текст вопроса", "answers": '
        '[{"text": "вариант", "is_correct": true|false}, ...]}\n'
        "Ровно 4 варианта ответа, ровно один правильный. Язык — русский."
    )
    prompt = (
        f"Курс: {course_title}\n\n"
        f"Материалы:\n{course_material[:12000]}\n\n"
        f"Сгенерируй {num_questions} вопросов на основе этих материалов."
    )
    resp = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=3000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(block.text for block in resp.content if block.type == "text").strip()
    data = _extract_json(raw)
    questions: list[dict] = []
    for i, item in enumerate(data):
        answers = item.get("answers", [])
        if not any(a.get("is_correct") for a in answers):
            continue
        questions.append(
            {
                "text": item.get("text", "").strip(),
                "order": i,
                "answers": [
                    {"text": a.get("text", "").strip(), "is_correct": bool(a.get("is_correct"))}
                    for a in answers
                    if a.get("text")
                ],
            }
        )
    if not questions:
        raise AIUnavailable("Не удалось сгенерировать вопросы — попробуйте ещё раз")
    return questions


def _extract_json(text: str) -> list:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        raise AIUnavailable("AI вернул некорректный формат ответа")
    return json.loads(text[start : end + 1])
