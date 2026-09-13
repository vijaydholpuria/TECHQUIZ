"""Important application behaviours, using an isolated SQLite database."""
import os
import sys
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TEST_DB = ROOT / "database" / "test_techquiz.db"
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "test-password"
os.environ["SECRET_KEY"] = "test-secret-only"

from backend.database import Base, SessionLocal, engine  # noqa: E402
from backend.main import app  # noqa: E402
from backend.models import Answer, Participant, Question, Quiz  # noqa: E402
from backend.services.cleanup import cleanup_expired_quizzes  # noqa: E402
from backend.services.quiz_engine import leaderboard  # noqa: E402
from backend.services.scoring import points_for_answer  # noqa: E402
from backend.time_utils import utcnow  # noqa: E402


QUESTION = {
    "question_text": "What does CPU stand for?",
    "option_a": "Central Processing Unit",
    "option_b": "Computer Personal Unit",
    "option_c": "Central Program Unit",
    "option_d": "Control Processing Unit",
    "correct_option": "A",
    "time_limit": 15,
}


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


def login(client):
    response = client.post("/api/admin/login", json={"username": "admin", "password": "test-password"})
    assert response.status_code == 200


def create_quiz(client, questions=None):
    login(client)
    response = client.post("/api/quizzes", json={"name": "Backend test quiz", "questions": questions or [QUESTION]})
    assert response.status_code == 201
    return response.json()["id"]


def test_admin_protection_and_quiz_creation(client):
    blocked = client.post("/api/quizzes", json={"name": "No access", "questions": [QUESTION]})
    assert blocked.status_code == 401
    assert client.get("/admin/dashboard", follow_redirects=False).status_code == 303
    quiz_id = create_quiz(client)
    details = client.get(f"/api/quizzes/{quiz_id}").json()
    assert details["name"] == "Backend test quiz"
    assert details["question_count"] == 1
    assert details["status"] == "WAITING"


def test_question_creation_and_idempotent_participant_join(client):
    quiz_id = create_quiz(client)
    new_question = {**QUESTION, "question_text": "Which language is interpreted?", "correct_option": "B"}
    add = client.post(f"/api/quizzes/{quiz_id}/questions", json=new_question)
    assert add.status_code == 201
    first = client.post(f"/api/quizzes/{quiz_id}/join", json={"name": "Vijay"})
    assert first.status_code == 201
    repeated = client.post(f"/api/quizzes/{quiz_id}/join", json={"name": "A different name is ignored", "participant_token": first.json()["participant_token"]})
    assert repeated.status_code == 201
    assert repeated.json()["participant_id"] == first.json()["participant_id"]
    assert client.get(f"/api/quizzes/{quiz_id}").json()["participant_count"] == 1


def test_scoring_examples_are_floored_correctly():
    assert points_for_answer(True, 15, 4) == 111
    assert points_for_answer(False, 15, 4) == 11
    assert points_for_answer(True, 15, 15) == 100
    assert points_for_answer(False, 15, 15) == 0
    assert points_for_answer(False, 15, 15.99) == 0
    assert points_for_answer(True, 15, 4.999) == 110


def test_server_accepts_one_in_time_answer_and_rejects_duplicate(client):
    quiz_id = create_quiz(client)
    participant = client.post(f"/api/quizzes/{quiz_id}/join", json={"name": "Priya"}).json()
    assert client.post(f"/api/admin/quizzes/{quiz_id}/start").status_code == 200
    db = SessionLocal()
    try:
        quiz = db.query(Quiz).filter_by(public_id=quiz_id).one()
        quiz.question_started_at = utcnow() - timedelta(seconds=4)
        quiz.question_ends_at = utcnow() + timedelta(seconds=11)
        question_id = quiz.questions[0].id
        db.commit()
    finally:
        db.close()
    payload = {"participant_token": participant["participant_token"], "question_id": question_id, "selected_option": "A"}
    answer = client.post(f"/api/quizzes/{quiz_id}/answer", json=payload)
    assert answer.status_code == 200
    assert "correct" not in answer.json()
    assert client.post(f"/api/quizzes/{quiz_id}/answer", json=payload).status_code == 409
    db = SessionLocal()
    try:
        stored = db.query(Answer).one()
        assert stored.is_correct is True
        assert 110 <= stored.points <= 111
    finally:
        db.close()


def test_timeout_and_started_quiz_join_are_rejected(client):
    quiz_id = create_quiz(client)
    participant = client.post(f"/api/quizzes/{quiz_id}/join", json={"name": "Aman"}).json()
    client.post(f"/api/admin/quizzes/{quiz_id}/start")
    assert client.post(f"/api/quizzes/{quiz_id}/join", json={"name": "Late player"}).status_code == 409
    db = SessionLocal()
    try:
        quiz = db.query(Quiz).filter_by(public_id=quiz_id).one()
        quiz.question_ends_at = utcnow() - timedelta(milliseconds=1)
        question_id = quiz.questions[0].id
        db.commit()
    finally:
        db.close()
    late = client.post(f"/api/quizzes/{quiz_id}/answer", json={"participant_token": participant["participant_token"], "question_id": question_id, "selected_option": "B"})
    assert late.status_code == 409


def test_authenticated_websocket_gets_live_question_without_answer_key(client):
    quiz_id = create_quiz(client)
    participant = client.post(f"/api/quizzes/{quiz_id}/join", json={"name": "Socket player"}).json()
    with client.websocket_connect(f"/ws/quiz/{quiz_id}?admin_mode=true") as host_socket:
        host_state = host_socket.receive_json()
        assert host_state["participants"][0]["name"] == "Socket player"
    with client.websocket_connect(f"/ws/quiz/{quiz_id}?participant_token={participant['participant_token']}") as websocket:
        waiting = websocket.receive_json()
        assert waiting["status"] == "WAITING"
        assert "question" not in waiting
        assert client.post(f"/api/admin/quizzes/{quiz_id}/start").status_code == 200
        assert websocket.receive_json()["type"] == "QUIZ_STARTED"
        active = websocket.receive_json()
        assert active["type"] == "STATE"
        assert active["question"]["question"] == QUESTION["question_text"]
        assert "correct_option" not in active["question"]


def test_ranking_uses_requested_tie_breakers():
    now = utcnow()
    quiz = SimpleNamespace(participants=[
        SimpleNamespace(name="Slow", total_score=210, correct_count=2, total_response_time=8.0, last_answer_at=now, joined_at=now, unanswered_count=0, wrong_count=0),
        SimpleNamespace(name="Fast", total_score=210, correct_count=2, total_response_time=6.0, last_answer_at=now, joined_at=now, unanswered_count=0, wrong_count=0),
        SimpleNamespace(name="Less correct", total_score=210, correct_count=1, total_response_time=2.0, last_answer_at=now, joined_at=now, unanswered_count=0, wrong_count=1),
    ])
    assert [row["name"] for row in leaderboard(quiz)] == ["Fast", "Slow", "Less correct"]


def test_expired_quiz_cleanup_cascades_to_all_related_rows():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        quiz = Quiz(public_id="TECH-OLD001", name="Expired", expires_at=utcnow() - timedelta(seconds=1))
        question = Question(quiz=quiz, question_number=1, **QUESTION)
        participant = Participant(quiz=quiz, name="Old player", session_token="x" * 32)
        answer = Answer(quiz=quiz, participant=participant, question=question, selected_option="A", is_correct=True, response_time=1.0, points=114)
        db.add_all([quiz, question, participant, answer])
        db.commit()
        assert cleanup_expired_quizzes(db) == 1
        assert db.query(Quiz).count() == 0
        assert db.query(Question).count() == 0
        assert db.query(Participant).count() == 0
        assert db.query(Answer).count() == 0
    finally:
        db.close()
