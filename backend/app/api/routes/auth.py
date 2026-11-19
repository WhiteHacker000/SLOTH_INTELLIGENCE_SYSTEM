import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.security import SettingsDep
from app.auth import sessions
from app.auth.access import (
    SESSION_COOKIE,
    CallerDep,
    optional_cipher,
    sign_in_configured,
)
from app.auth.crypto import TokenCipher
from app.auth.github import GitHubSignIn, SignInFailed
from app.core.config import Settings
from app.db.session import get_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

STATE_COOKIE = "sils_sign_in_state"
STATE_MAX_AGE = 600


class SignedInUser(BaseModel):
    login: str
    avatar_url: str | None


class AuthStatus(BaseModel):
    sign_in_enabled: bool
    user: SignedInUser | None


def get_github_sign_in(settings: SettingsDep) -> GitHubSignIn:
    if not sign_in_configured(settings):
        raise HTTPException(503, "Sign-in is not set up on this server")
    assert settings.github_app_client_id and settings.github_app_client_secret
    return GitHubSignIn(
        settings.github_app_client_id,
        settings.github_app_client_secret.get_secret_value(),
        f"{settings.public_url}/api/v1/auth/callback",
        settings.github_api_base_url,
    )


GitHubDep = Annotated[GitHubSignIn, Depends(get_github_sign_in)]
SessionDep = Annotated[Session, Depends(get_session)]
CipherDep = Annotated[TokenCipher | None, Depends(optional_cipher)]


@router.get("/login")
def login(github: GitHubDep, settings: SettingsDep) -> RedirectResponse:
    state = secrets.token_urlsafe(32)
    response = RedirectResponse(github.authorize_url(state), status_code=302)
    response.set_cookie(
        STATE_COOKIE,
        state,
        max_age=STATE_MAX_AGE,
        path="/api/v1/auth",
        httponly=True,
        samesite="lax",
        secure=_secure(settings),
    )
    return response


@router.get("/callback")
def callback(
    github: GitHubDep,
    settings: SettingsDep,
    session: SessionDep,
    cipher: CipherDep,
    code: Annotated[str, Query(max_length=200)],
    state: Annotated[str, Query(max_length=200)],
    expected: Annotated[str | None, Cookie(alias=STATE_COOKIE)] = None,
) -> RedirectResponse:
    # The state must match the cookie set by /login in this browser, so a
    # link from someone else cannot sign this browser in as them.
    if not expected or not secrets.compare_digest(state, expected):
        raise HTTPException(400, "Sign-in expired or was started elsewhere")
    assert cipher is not None  # get_github_sign_in checked the key is set
    try:
        token = github.exchange_code(code)
        profile = github.fetch_user(token.value)
    except SignInFailed as error:
        logger.warning("Sign-in failed: %s", error)
        raise HTTPException(502, "GitHub sign-in failed, please try again") from None
    user = sessions.save_user(
        session, profile.github_id, profile.login, profile.avatar_url
    )
    cookie = sessions.start_session(session, cipher, user, token.value, token.lifetime)
    session.commit()
    logger.info("Signed in %s", profile.login)

    response = RedirectResponse(settings.app_url, status_code=302)
    response.delete_cookie(STATE_COOKIE, path="/api/v1/auth")
    response.set_cookie(
        SESSION_COOKIE,
        cookie,
        max_age=int(token.lifetime.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=_secure(settings),
    )
    return response


@router.post("/logout", status_code=204)
def logout(
    session: SessionDep,
    response: Response,
    cookie: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> None:
    if cookie:
        sessions.end_session(session, cookie)
        session.commit()
    response.delete_cookie(SESSION_COOKIE)


@router.get("/me", response_model=AuthStatus)
def me(settings: SettingsDep, caller: CallerDep) -> AuthStatus:
    found = caller.user
    user = found and SignedInUser(
        login=found.user.login, avatar_url=found.user.avatar_url
    )
    return AuthStatus(sign_in_enabled=sign_in_configured(settings), user=user or None)


def _secure(settings: Settings) -> bool:
    return settings.public_url.startswith("https://")
