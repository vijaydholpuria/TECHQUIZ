import bcrypt

from fastapi import HTTPException, Request, status

from .config import ADMIN_PASSWORD, ADMIN_PASSWORD_HASH, ADMIN_USERNAME

# Production can provide a precomputed bcrypt hash. For simple development setup,
# hash the password supplied through the environment once at process startup.
_configured_hash = ADMIN_PASSWORD_HASH.encode() if ADMIN_PASSWORD_HASH else bcrypt.hashpw(ADMIN_PASSWORD.encode(), bcrypt.gensalt())


def verify_admin(username: str, password: str) -> bool:
    # Hashing is deliberately performed server-side; credentials never reach browser code.
    password_bytes = password.encode()
    if len(password_bytes) > 72:
        return False
    return username == ADMIN_USERNAME and bcrypt.checkpw(password_bytes, _configured_hash)


def require_admin(request: Request):
    if not request.session.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin authentication required.")
    return True
