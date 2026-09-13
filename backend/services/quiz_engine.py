import asyncio
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import QUIZ_RETENTION_HOURS
from ..database import SessionLocal
from ..models import Answer, Participant, Question, Quiz
from ..time_utils import utcnow
from ..websocket.manager import manager
from .scoring import points_for_answer, ranking_key

_timer_tasks: dict[str, asyncio.Task] = {}


def cancel_all_timer_tasks():
    """Stop outstanding in-process question timers during a clean server shutdown."""
    for task in _timer_tasks.values():
        if not task.done():
            task.cancel()
    _timer_tasks.clear()


def generate_public_id() -> str:
    return f"TECH-{secrets.token_hex(3).upper()}"


def get_live_question(quiz: Quiz) -> Question | None:
    if quiz.current_question < 1:
        return None
    return next((question for question in quiz.questions if question.question_number == quiz.current_question), None)


def public_question(question: Question) -> dict:
    """The only question representation participant clients receive: no answer key."""
    return {
        "id": question.id,
        "number": question.question_number,
        "question": question.question_text,
        "options": {"A": question.option_a, "B": question.option_b, "C": question.option_c, "D": question.option_d},
        "time_limit": question.time_limit,
    }


def quiz_state(quiz: Quiz, participant: Participant | None = None, include_participants: bool = False) -> dict:
    current = get_live_question(quiz)
    payload = {
        "type": "STATE",
        "quiz_id": quiz.public_id,
        "name": quiz.name,
        "status": quiz.status,
        "current_question": quiz.current_question,
        "total_questions": len(quiz.questions),
        "participant_count": len(quiz.participants),
        "server_time": utcnow().isoformat() + "Z",
    }
    if quiz.status == "QUESTION_ACTIVE" and current:
        payload["question"] = public_question(current)
        payload["start_time"] = quiz.question_started_at.isoformat() + "Z"
        payload["end_time"] = quiz.question_ends_at.isoformat() + "Z"
        payload["answered_count"] = sum(1 for answer in current.answers)
        if participant:
            payload["has_answered"] = any(answer.question_id == current.id for answer in participant.answers)
    if include_participants:
        payload["participants"] = [{"id": item.id, "name": item.name, "joined_at": item.joined_at.isoformat() + "Z"} for item in sorted(quiz.participants, key=lambda item: item.joined_at)]
    return payload


async def broadcast_state(quiz_id: str):
    db = SessionLocal()
    try:
        quiz = db.query(Quiz).filter_by(id=quiz_id).first()
        if quiz:
            await manager.broadcast(quiz_id, quiz_state(quiz))
    finally:
        db.close()


def create_quiz(db: Session, name: str, question_inputs) -> Quiz:
    clean_name = " ".join(name.strip().split())
    if not clean_name:
        raise HTTPException(422, "Quiz name is required.")
    public_id = generate_public_id()
    while db.query(Quiz).filter_by(public_id=public_id).first():
        public_id = generate_public_id()
    quiz = Quiz(
        public_id=public_id,
        name=clean_name,
        status="WAITING",
        expires_at=utcnow() + timedelta(hours=QUIZ_RETENTION_HOURS),
    )
    for number, question in enumerate(question_inputs, start=1):
        quiz.questions.append(Question(question_number=number, **question.model_dump()))
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return quiz


def find_available_quiz(db: Session, public_id: str) -> Quiz:
    quiz = db.query(Quiz).filter_by(public_id=public_id).first()
    if not quiz:
        raise HTTPException(404, "Quiz not found.")
    if quiz.expires_at < utcnow():
        quiz.status = "EXPIRED"
        db.commit()
        raise HTTPException(410, "This quiz has expired.")
    return quiz


def join_quiz(db: Session, quiz: Quiz, name: str, participant_token: str | None = None) -> Participant:
    if quiz.status != "WAITING":
        raise HTTPException(409, "This quiz has already started.")
    if participant_token:
        existing = db.query(Participant).filter_by(quiz_id=quiz.id, session_token=participant_token).first()
        if existing:
            return existing
    participant = Participant(name=name, quiz_id=quiz.id, session_token=secrets.token_urlsafe(32))
    db.add(participant)
    db.commit()
    db.refresh(participant)
    return participant


async def start_quiz(db: Session, quiz: Quiz):
    if quiz.status != "WAITING":
        raise HTTPException(409, "Quiz cannot be started in its current state.")
    if not quiz.questions:
        raise HTTPException(422, "Add at least one question before starting.")
    quiz.status = "RUNNING"
    quiz.started_at = utcnow()
    db.commit()
    await manager.broadcast(quiz.id, {"type": "QUIZ_STARTED"})
    _activate_question(db, quiz, 1)
    await broadcast_state(quiz.id)
    _schedule_timer(quiz.id)


def _activate_question(db: Session, quiz: Quiz, number: int):
    question = next((item for item in quiz.questions if item.question_number == number), None)
    if not question:
        raise HTTPException(500, "Question sequence is invalid.")
    started = utcnow()
    quiz.status = "QUESTION_ACTIVE"
    quiz.current_question = number
    quiz.question_started_at = started
    quiz.question_ends_at = started + timedelta(seconds=question.time_limit)
    db.commit()
    db.refresh(quiz)


def _schedule_timer(quiz_id: str):
    existing = _timer_tasks.get(quiz_id)
    if existing and not existing.done():
        existing.cancel()
    _timer_tasks[quiz_id] = asyncio.create_task(_advance_after_deadline(quiz_id))


async def _advance_after_deadline(quiz_id: str):
    db = SessionLocal()
    try:
        quiz = db.query(Quiz).filter_by(id=quiz_id).first()
        if not quiz or quiz.status != "QUESTION_ACTIVE" or not quiz.question_ends_at:
            return
        delay = max(0, (quiz.question_ends_at - utcnow()).total_seconds())
    finally:
        db.close()
    await asyncio.sleep(delay)
    db = SessionLocal()
    try:
        quiz = db.query(Quiz).filter_by(id=quiz_id).first()
        if not quiz or quiz.status != "QUESTION_ACTIVE" or quiz.question_ends_at > utcnow():
            return
        await manager.broadcast(quiz_id, {"type": "QUESTION_ENDED", "question_number": quiz.current_question})
        if quiz.current_question < len(quiz.questions):
            _activate_question(db, quiz, quiz.current_question + 1)
            fresh_question = get_live_question(quiz)
            await manager.broadcast(quiz_id, {"type": "QUESTION_STARTED", "question": public_question(fresh_question), "start_time": quiz.question_started_at.isoformat() + "Z", "end_time": quiz.question_ends_at.isoformat() + "Z"})
            await broadcast_state(quiz_id)
            _schedule_timer(quiz_id)
        else:
            _finish_quiz(db, quiz)
            await manager.broadcast(quiz_id, {"type": "QUIZ_FINISHED"})
            await broadcast_state(quiz_id)
    finally:
        db.close()


def _finish_quiz(db: Session, quiz: Quiz):
    if quiz.status == "FINISHED":
        return
    question_count = len(quiz.questions)
    for participant in quiz.participants:
        participant.unanswered_count = max(0, question_count - len(participant.answers))
    quiz.status = "FINISHED"
    quiz.finished_at = utcnow()
    quiz.question_ends_at = utcnow()
    db.commit()


async def end_quiz(db: Session, quiz: Quiz):
    if quiz.status not in {"QUESTION_ACTIVE", "WAITING"}:
        raise HTTPException(409, "Quiz cannot be ended in its current state.")
    task = _timer_tasks.get(quiz.id)
    if task and not task.done():
        task.cancel()
    _finish_quiz(db, quiz)
    await manager.broadcast(quiz.id, {"type": "QUIZ_FINISHED"})
    await broadcast_state(quiz.id)


async def submit_answer(db: Session, quiz: Quiz, token: str, question_id: str, selected: str) -> dict:
    participant = db.query(Participant).filter_by(quiz_id=quiz.id, session_token=token).first()
    if not participant:
        raise HTTPException(401, "Invalid participant session.")
    if quiz.status != "QUESTION_ACTIVE" or quiz.question_ends_at is None or utcnow() >= quiz.question_ends_at:
        raise HTTPException(409, "Time is over.")
    question = get_live_question(quiz)
    if not question or question.id != question_id:
        raise HTTPException(409, "This question is no longer active.")
    if db.query(Answer).filter_by(participant_id=participant.id, question_id=question.id).first():
        raise HTTPException(409, "An answer has already been submitted.")
    response_time = max(0.0, (utcnow() - quiz.question_started_at).total_seconds())
    is_correct = selected == question.correct_option
    points = points_for_answer(is_correct, question.time_limit, response_time)
    answer = Answer(quiz_id=quiz.id, participant_id=participant.id, question_id=question.id, selected_option=selected, is_correct=is_correct, response_time=response_time, points=points)
    db.add(answer)
    participant.total_score += points
    participant.total_response_time += response_time
    participant.correct_count += int(is_correct)
    participant.wrong_count += int(not is_correct)
    participant.last_answer_at = utcnow()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An answer has already been submitted.")
    await manager.broadcast(quiz.id, {"type": "PARTICIPANT_PROGRESS", "answered_count": db.query(func.count(Answer.id)).filter_by(quiz_id=quiz.id, question_id=question.id).scalar()})
    # Only report an acknowledgement, never the correctness or points, before expiry.
    return {"message": "Answer submitted and locked.", "question_id": question.id}


def leaderboard(quiz: Quiz) -> list[dict]:
    ordered = sorted(quiz.participants, key=ranking_key)
    return [
        {
            "rank": index,
            "name": participant.name,
            "score": participant.total_score,
            "correct": participant.correct_count,
            "wrong": participant.wrong_count,
            "unanswered": participant.unanswered_count,
            "total_response_time": round(participant.total_response_time, 2),
        }
        for index, participant in enumerate(ordered, start=1)
    ]


def participant_result(quiz: Quiz, participant: Participant) -> dict:
    ordered = sorted(quiz.participants, key=ranking_key)
    rank = ordered.index(participant) + 1
    return {
        "rank": rank,
        "name": participant.name,
        "score": participant.total_score,
        "correct": participant.correct_count,
        "wrong": participant.wrong_count,
        "unanswered": participant.unanswered_count,
        "total_response_time": round(participant.total_response_time, 2),
        "status": quiz.status,
    }
