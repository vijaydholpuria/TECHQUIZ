import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

def sqlalchemy_database_url(url: str) -> str:
    """Accept the Postgres URL copied from Supabase and select psycopg for SQLAlchemy."""
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    return url


# Set DATABASE_URL in .env to the direct or session-pooler URI from Supabase.
# SQLite remains a convenient local fallback for development and automated tests.
DATABASE_URL = sqlalchemy_database_url(os.getenv("DATABASE_URL", f"sqlite:///{(ROOT_DIR / 'database' / 'techquiz.db').as_posix()}"))
DATABASE_POOL_SIZE = int(os.getenv("DATABASE_POOL_SIZE", "5"))
DATABASE_MAX_OVERFLOW = int(os.getenv("DATABASE_MAX_OVERFLOW", "5"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me-in-production")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
SECRET_KEY = os.getenv("SECRET_KEY", "replace-this-development-secret")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
QUIZ_RETENTION_HOURS = int(os.getenv("QUIZ_RETENTION_HOURS", "24"))
MAX_QUESTIONS = int(os.getenv("MAX_QUESTIONS", "100"))
