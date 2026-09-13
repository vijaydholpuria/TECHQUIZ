from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import Participant
from ..schemas import AnswerInput, JoinInput, QuestionInput, QuizInput
from ..services.qr_generator import create_qr_png, join_url
from ..services.quiz_engine import create_quiz, find_available_quiz, join_quiz, leaderboard, participant_result, public_question, quiz_state, submit_answer
from ..websocket.manager import manager

router = APIRouter(prefix="/api/quizzes", tags=["quizzes"])


@router.post("", status_code=201)
def create(payload: QuizInput, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    quiz = create_quiz(db, payload.name, payload.questions)
    return {"id": quiz.public_id, "name": quiz.name, "status": quiz.status, "join_url": join_url(quiz.public_id)}


@router.post("/{quiz_id}/questions", status_code=201)
def add_question(quiz_id: str, payload: QuestionInput, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    quiz = find_available_quiz(db, quiz_id)
    if quiz.status != "WAITING":
        raise HTTPException(409, "Questions can only be added before the quiz starts.")
    if len(quiz.questions) >= 100:
        raise HTTPException(422, "Maximum question limit reached.")
    from ..models import Question
    question = Question(quiz_id=quiz.id, question_number=len(quiz.questions) + 1, **payload.model_dump())
    db.add(question)
    db.commit()
    return {"id": question.id, "question_number": question.question_number}


@router.get("/{quiz_id}")
def quiz_details(quiz_id: str, db: Session = Depends(get_db)):
    quiz = find_available_quiz(db, quiz_id)
    return {"id": quiz.public_id, "name": quiz.name, "status": quiz.status, "participant_count": len(quiz.participants), "question_count": len(quiz.questions)}


@router.get("/{quiz_id}/qr")
def qr(quiz_id: str, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    quiz = find_available_quiz(db, quiz_id)
    return Response(create_qr_png(quiz.public_id), media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/{quiz_id}/join", status_code=201)
async def join(quiz_id: str, payload: JoinInput, db: Session = Depends(get_db)):
    quiz = find_available_quiz(db, quiz_id)
    participant = join_quiz(db, quiz, payload.name, payload.participant_token)
    await manager.broadcast(quiz.id, {"type": "PARTICIPANT_COUNT", "participant_count": len(quiz.participants)})
    return {"message": "You're successfully joined!", "participant_id": participant.id, "participant_token": participant.session_token, "name": participant.name, "quiz_id": quiz.public_id}


@router.post("/{quiz_id}/answer")
async def answer(quiz_id: str, payload: AnswerInput, db: Session = Depends(get_db)):
    quiz = find_available_quiz(db, quiz_id)
    return await submit_answer(db, quiz, payload.participant_token, payload.question_id, payload.selected_option)


@router.get("/{quiz_id}/state")
def state(quiz_id: str, participant_token: str | None = None, db: Session = Depends(get_db)):
    quiz = find_available_quiz(db, quiz_id)
    participant = None
    if participant_token:
        participant = db.query(Participant).filter_by(quiz_id=quiz.id, session_token=participant_token).first()
        if not participant:
            raise HTTPException(401, "Invalid participant session.")
    return quiz_state(quiz, participant=participant)


@router.get("/{quiz_id}/my-result")
def my_result(quiz_id: str, participant_token: str, db: Session = Depends(get_db)):
    quiz = find_available_quiz(db, quiz_id)
    participant = db.query(Participant).filter_by(quiz_id=quiz.id, session_token=participant_token).first()
    if not participant:
        raise HTTPException(401, "Invalid participant session.")
    if quiz.status != "FINISHED":
        return {"status": quiz.status, "message": "Calculating results..."}
    return participant_result(quiz, participant)


@router.get("/{quiz_id}/leaderboard")
def public_leaderboard(quiz_id: str, db: Session = Depends(get_db)):
    quiz = find_available_quiz(db, quiz_id)
    if quiz.status != "FINISHED":
        raise HTTPException(409, "Results are not ready yet.")
    return {"quiz_id": quiz.public_id, "leaderboard": leaderboard(quiz)}
