import csv
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from ..auth import require_admin, verify_admin
from ..database import get_db
from ..models import Quiz
from ..schemas import LoginPayload
from ..services.quiz_engine import end_quiz, find_available_quiz, leaderboard, start_quiz

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/login")
def login(payload: LoginPayload, request: Request, response: Response):
    if not verify_admin(payload.username, payload.password):
        raise HTTPException(401, "Invalid username or password.")
    request.session.clear()
    request.session["is_admin"] = True
    request.session["username"] = payload.username
    return {"message": "Logged in successfully.", "username": payload.username}


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"message": "Logged out successfully."}


@router.get("/me")
def me(request: Request, _admin=Depends(require_admin)):
    return {"username": request.session.get("username")}


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    quizzes = db.query(Quiz).order_by(Quiz.created_at.desc()).all()
    active = [quiz for quiz in quizzes if quiz.status in {"WAITING", "QUESTION_ACTIVE"}]
    latest = active[0] if active else (quizzes[0] if quizzes else None)
    return {
        "total_active_quizzes": len(active),
        "current_participants": sum(len(quiz.participants) for quiz in active),
        "current_status": latest.status if latest else "NO QUIZ",
        "total_questions": len(latest.questions) if latest else 0,
        "active_quiz": quiz_summary(latest) if latest else None,
    }


def quiz_summary(quiz: Quiz) -> dict:
    return {
        "id": quiz.public_id,
        "name": quiz.name,
        "status": quiz.status,
        "question_count": len(quiz.questions),
        "participant_count": len(quiz.participants),
        "current_question": quiz.current_question,
    }


@router.get("/quizzes/{quiz_id}/participants")
def participants(quiz_id: str, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    quiz = find_available_quiz(db, quiz_id)
    return {"total": len(quiz.participants), "participants": [{"name": person.name, "joined_at": person.joined_at.isoformat() + "Z"} for person in sorted(quiz.participants, key=lambda person: person.joined_at)]}


@router.post("/quizzes/{quiz_id}/start")
async def start(quiz_id: str, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    quiz = find_available_quiz(db, quiz_id)
    await start_quiz(db, quiz)
    return {"message": "Quiz started.", "status": "QUESTION_ACTIVE"}


@router.post("/quizzes/{quiz_id}/end")
async def end(quiz_id: str, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    quiz = find_available_quiz(db, quiz_id)
    await end_quiz(db, quiz)
    return {"message": "Quiz finalized.", "status": "FINISHED"}


@router.get("/quizzes/{quiz_id}/results")
def results(quiz_id: str, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    quiz = find_available_quiz(db, quiz_id)
    return {"quiz": quiz_summary(quiz), "leaderboard": leaderboard(quiz)}


@router.get("/quizzes/{quiz_id}/results.csv")
def export_results(quiz_id: str, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    quiz = find_available_quiz(db, quiz_id)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Rank", "Participant Name", "Total Score", "Correct Answers", "Wrong Answers", "Unanswered", "Total Response Time"])
    for row in leaderboard(quiz):
        writer.writerow([row["rank"], row["name"], row["score"], row["correct"], row["wrong"], row["unanswered"], row["total_response_time"]])
    filename = f"techquiz-{quiz.public_id}-results.csv"
    return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
