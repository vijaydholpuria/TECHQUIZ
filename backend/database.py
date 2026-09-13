from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_MAX_OVERFLOW, DATABASE_POOL_SIZE, DATABASE_URL


class Base(DeclarativeBase):
    pass


is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}
engine_options = {"connect_args": connect_args, "pool_pre_ping": True}
if not is_sqlite:
    # Sensible limits for a persistent FastAPI server using Supabase Postgres.
    engine_options.update({"pool_size": DATABASE_POOL_SIZE, "max_overflow": DATABASE_MAX_OVERFLOW})
engine = create_engine(DATABASE_URL, **engine_options)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    if is_sqlite:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
