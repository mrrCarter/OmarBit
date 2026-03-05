import datetime
import os
import uuid

from fastapi import HTTPException, Request
from jose import JWTError, jwt

JWT_ALGORITHM = "HS256"


def _get_secret() -> str:
    return os.getenv("NEXTAUTH_SECRET", "")


class AuthenticatedUser:
    __slots__ = ("id", "github_id", "username")

    def __init__(self, *, id: str, github_id: str, username: str) -> None:
        self.id = id
        self.github_id = github_id
        self.username = username


def _error_envelope(request: Request, code: str, message: str, status: int) -> HTTPException:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return HTTPException(
        status_code=status,
        detail={
            "error": {"code": code, "message": message},
            "requestId": request_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
    )


async def get_current_user(request: Request) -> AuthenticatedUser:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise _error_envelope(request, "UNAUTHORIZED", "Missing or invalid authorization header", 401)

    token = auth_header[7:]
    secret = _get_secret()
    if not secret:
        raise _error_envelope(request, "SERVER_CONFIG_ERROR", "Auth secret not configured", 500)

    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise _error_envelope(request, "UNAUTHORIZED", "Invalid or expired token", 401)

    github_id = payload.get("github_id")
    username = payload.get("username")
    user_id = payload.get("user_id")
    if not github_id or not username:
        raise _error_envelope(request, "UNAUTHORIZED", "Token missing required claims", 401)

    return AuthenticatedUser(id=user_id or "", github_id=str(github_id), username=str(username))
