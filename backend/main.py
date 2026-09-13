import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import SECRET_KEY
from .database import Base, SessionLocal, engine
from .models import Participant, Quiz
from .routes import admin, quiz
from .services.cleanup import cleanup_expired_quizzes
from .services.quiz_engine import _schedule_timer, cancel_all_timer_tasks, find_available_quiz, quiz_state
from .websocket.manager import manager

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"


async def cleanup_loop():
    while True:
        await asyncio.sleep(15 * 60)
        db = SessionLocal()
        try:
            cleanup_expired_quizzes(db)
        finally:
            db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        cleanup_expired_quizzes(db)
        for active_quiz in db.query(Quiz).filter_by(status="QUESTION_ACTIVE").all():
            _schedule_timer(active_quiz.id)
    finally:
        db.close()
    task = asyncio.create_task(cleanup_loop())
    yield
    task.cancel()
    cancel_all_timer_tasks()


app = FastAPI(title="TechQuiz", version="1.0.0", lifespan=lifespan)
FRONTEND_URL = os.getenv("FRONTEND_URL", "")

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    max_age=60 * 60 * 12,
    same_site=os.getenv("COOKIE_SAME_SITE", "lax"),
    https_only=os.getenv("COOKIE_SECURE", "false").lower() == "true",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL] if FRONTEND_URL else [],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(admin.router)
app.include_router(quiz.router)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


def page(path: str) -> FileResponse:
    return FileResponse(FRONTEND_DIR / path)


def admin_page(request: Request, path: str):
    if not request.session.get("is_admin"):
        return RedirectResponse("/admin/login", status_code=303)
    return page(path)


@app.get("/", include_in_schema=False)
def home():
    return page("index.html")


@app.get("/join/{quiz_id}", include_in_schema=False)
def join_page(quiz_id: str):
    return page("user/join.html")


@app.get("/admin/login", include_in_schema=False)
def admin_login_page():
    return page("admin/login.html")


@app.get("/admin/dashboard", include_in_schema=False)
def dashboard_page(request: Request):
    return admin_page(request, "admin/dashboard.html")


@app.get("/admin/create-quiz", include_in_schema=False)
def create_quiz_page(request: Request):
    return admin_page(request, "admin/create-quiz.html")


@app.get("/admin/quiz/{quiz_id}/qr", include_in_schema=False)
def qr_page(quiz_id: str, request: Request):
    return admin_page(request, "admin/qr.html")


@app.get("/admin/quiz/{quiz_id}/live", include_in_schema=False)
def live_page(quiz_id: str, request: Request):
    return admin_page(request, "admin/live.html")


@app.get("/admin/quiz/{quiz_id}/results", include_in_schema=False)
def results_page(quiz_id: str, request: Request):
    return admin_page(request, "admin/results.html")


@app.websocket("/ws/quiz/{quiz_id}")
async def quiz_websocket(websocket: WebSocket, quiz_id: str, participant_token: str | None = None, admin_mode: bool = False):
    """Authenticated realtime state stream. It never sends the answer key."""
    db = SessionLocal()
    participant = None
    is_admin = bool(websocket.scope.get("session", {}).get("is_admin")) and admin_mode
    try:
        quiz_record = find_available_quiz(db, quiz_id)
        if not is_admin:
            if not participant_token:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            participant = db.query(Participant).filter_by(quiz_id=quiz_record.id, session_token=participant_token).first()
            if not participant:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
        await manager.connect(quiz_record.id, websocket)
        await websocket.send_json(quiz_state(quiz_record, participant=participant, include_participants=is_admin))
    except Exception:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return
    finally:
        db.close()

    try:
        while True:
            # Reading keeps the connection alive and gives clients a lightweight ping channel.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(quiz_record.id, websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
