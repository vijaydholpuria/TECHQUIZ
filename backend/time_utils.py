from datetime import UTC, datetime


def utcnow() -> datetime:
    """UTC time stored as a naive value for SQLite compatibility."""
    return datetime.now(UTC).replace(tzinfo=None)
