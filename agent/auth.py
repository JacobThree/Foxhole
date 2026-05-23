import hmac
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from agent.settings import AppSettings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    bearer_token: str = Field(min_length=1)


class AuthSessionResponse(BaseModel):
    authenticated: bool
    cookie_name: str


def validate_bearer_token(token: str, settings: AppSettings) -> None:
    if not settings.api_auth_configured or settings.api_bearer_token is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API bearer token is not configured.",
        )

    expected = settings.api_bearer_token.get_secret_value()
    if not secrets.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def session_cookie_value(settings: AppSettings) -> str:
    if not settings.api_auth_configured or settings.api_bearer_token is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API bearer token is not configured.",
        )
    secret = settings.api_bearer_token.get_secret_value().encode()
    signature = hmac.digest(secret, b"foxhole-session:v1", "sha256").hex()
    return f"v1:{signature}"


def session_cookie_is_valid(value: str | None, settings: AppSettings) -> bool:
    if value is None:
        return False
    try:
        expected = session_cookie_value(settings)
    except HTTPException:
        return False
    return secrets.compare_digest(value, expected)


def set_session_cookie(response: Response, settings: AppSettings) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=session_cookie_value(settings),
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


def clear_session_cookie(response: Response, settings: AppSettings) -> None:
    response.delete_cookie(
        key=settings.cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


def login_with_bearer_token(
    request: LoginRequest,
    response: Response,
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> AuthSessionResponse:
    validate_bearer_token(request.bearer_token, settings)
    set_session_cookie(response, settings)
    return AuthSessionResponse(authenticated=True, cookie_name=settings.cookie_name)


def logout_session(
    response: Response,
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> AuthSessionResponse:
    clear_session_cookie(response, settings)
    return AuthSessionResponse(authenticated=False, cookie_name=settings.cookie_name)


def require_bearer_token(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> None:
    if not settings.api_auth_configured or settings.api_bearer_token is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API bearer token is not configured.",
        )

    if session_cookie_is_valid(request.cookies.get(settings.cookie_name), settings):
        return

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    validate_bearer_token(credentials.credentials, settings)
