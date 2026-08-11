"""Pydantic-схемы (v2) для валидации и сериализации."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import EnrollmentStatus, UserRole


# ---------- Auth / Users ----------
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    department: str | None = None
    position: str | None = None


class UserCreate(UserBase):
    password: str = Field(min_length=6)
    role: UserRole = UserRole.student


class UserRegister(BaseModel):
    email: EmailStr
    full_name: str
    password: str = Field(min_length=6)


class UserUpdate(BaseModel):
    full_name: str | None = None
    department: str | None = None
    position: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=6)


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: UserRole
    is_active: bool
    created_at: datetime


# ---------- Lessons ----------
class LessonBase(BaseModel):
    title: str
    content: str = ""
    video_url: str | None = None
    order: int = 0


class LessonCreate(LessonBase):
    pass


class LessonUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    video_url: str | None = None
    order: int | None = None


class LessonOut(LessonBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    course_id: int


# ---------- Quiz ----------
class AnswerBase(BaseModel):
    text: str
    is_correct: bool = False


class AnswerOut(BaseModel):
    """Ответ без флага правильности — для студента."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    text: str


class QuestionCreate(BaseModel):
    text: str
    order: int = 0
    answers: list[AnswerBase]


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    text: str
    order: int
    answers: list[AnswerOut]


class QuizCreate(BaseModel):
    title: str = "Итоговый тест"
    time_limit_minutes: int = 0
    questions: list[QuestionCreate] = []


class QuizOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    course_id: int
    title: str
    time_limit_minutes: int
    questions: list[QuestionOut]


class SubmittedAnswer(BaseModel):
    question_id: int
    answer_id: int


class QuizSubmission(BaseModel):
    answers: list[SubmittedAnswer]


class QuizResult(BaseModel):
    score: float
    passed: bool
    correct: int
    total: int
    certificate_id: int | None = None


# ---------- Courses ----------
class CourseBase(BaseModel):
    title: str
    description: str = ""
    category: str = "Общее"
    cover_url: str | None = None
    pass_score: int = 80
    certificate_enabled: bool = True


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    category: str | None = None
    cover_url: str | None = None
    pass_score: int | None = None
    certificate_enabled: bool | None = None
    is_published: bool | None = None


class CourseOut(CourseBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_published: bool
    created_at: datetime
    lessons_count: int = 0
    has_quiz: bool = False


class CourseDetail(CourseOut):
    lessons: list[LessonOut] = []


# ---------- Enrollments ----------
class EnrollmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    course_id: int
    status: EnrollmentStatus
    progress: float
    enrolled_at: datetime
    completed_at: datetime | None = None


class MyCourseOut(BaseModel):
    """Курс + прогресс текущего пользователя."""
    course: CourseOut
    enrollment: EnrollmentOut


# ---------- Certificates ----------
class CertificateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    course_id: int
    serial_number: str
    score: float
    issued_at: datetime
    course_title: str | None = None
    user_name: str | None = None


# ---------- AI ----------
class AIChatRequest(BaseModel):
    course_id: int
    message: str
    history: list[dict] = []


class AIChatResponse(BaseModel):
    reply: str


class AIGenerateQuizRequest(BaseModel):
    course_id: int
    num_questions: int = Field(default=5, ge=1, le=20)


# ---------- Analytics ----------
class OverviewStats(BaseModel):
    total_users: int
    total_courses: int
    total_enrollments: int
    completed_enrollments: int
    certificates_issued: int
    completion_rate: float


class CourseStat(BaseModel):
    course_id: int
    title: str
    category: str
    enrolled: int
    completed: int
    avg_progress: float
    avg_score: float | None = None


class UserProgressStat(BaseModel):
    user_id: int
    full_name: str
    department: str | None = None
    enrolled: int
    completed: int
    avg_progress: float
