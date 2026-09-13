import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .time_utils import utcnow


def uuid_text() -> str:
    return str(uuid.uuid4())


class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    public_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(24), default="WAITING", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    current_question: Mapped[int] = mapped_column(Integer, default=0)
    question_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    question_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    questions: Mapped[list["Question"]] = relationship(back_populates="quiz", cascade="all, delete-orphan", order_by="Question.question_number")
    participants: Mapped[list["Participant"]] = relationship(back_populates="quiz", cascade="all, delete-orphan")
    answers: Mapped[list["Answer"]] = relationship(back_populates="quiz", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("quiz_id", "question_number", name="uq_question_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    quiz_id: Mapped[str] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"), index=True)
    question_number: Mapped[int] = mapped_column(Integer)
    question_text: Mapped[str] = mapped_column(Text)
    option_a: Mapped[str] = mapped_column(String(500))
    option_b: Mapped[str] = mapped_column(String(500))
    option_c: Mapped[str] = mapped_column(String(500))
    option_d: Mapped[str] = mapped_column(String(500))
    correct_option: Mapped[str] = mapped_column(String(1))
    time_limit: Mapped[int] = mapped_column(Integer)

    quiz: Mapped[Quiz] = relationship(back_populates="questions")
    answers: Mapped[list["Answer"]] = relationship(back_populates="question", cascade="all, delete-orphan")


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (Index("ix_participant_quiz_token", "quiz_id", "session_token", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    quiz_id: Mapped[str] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    session_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    total_score: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)
    unanswered_count: Mapped[int] = mapped_column(Integer, default=0)
    total_response_time: Mapped[float] = mapped_column(Float, default=0.0)
    last_answer_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    quiz: Mapped[Quiz] = relationship(back_populates="participants")
    answers: Mapped[list["Answer"]] = relationship(back_populates="participant", cascade="all, delete-orphan")


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("participant_id", "question_id", name="uq_participant_question_answer"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    quiz_id: Mapped[str] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"), index=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    selected_option: Mapped[str] = mapped_column(String(1))
    is_correct: Mapped[bool] = mapped_column(Boolean)
    response_time: Mapped[float] = mapped_column(Float)
    points: Mapped[int] = mapped_column(Integer)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    quiz: Mapped[Quiz] = relationship(back_populates="answers")
    participant: Mapped[Participant] = relationship(back_populates="answers")
    question: Mapped[Question] = relationship(back_populates="answers")
