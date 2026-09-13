from sqlalchemy.orm import Session

from ..models import Quiz
from ..time_utils import utcnow


def cleanup_expired_quizzes(db: Session) -> int:
    """Cascade deletion removes questions, participants, answers, and their rankings."""
    expired = db.query(Quiz).filter(Quiz.expires_at < utcnow()).all()
    for quiz in expired:
        db.delete(quiz)
    db.commit()
    return len(expired)
