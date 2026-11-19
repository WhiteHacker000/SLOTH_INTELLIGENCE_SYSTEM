"""Who is calling, and what they may do.

Without sign-in configured (local use), the admin key works as before: open
when no key is set. With sign-in, changes need a signed-in user or the admin key.
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.security import (
    AdminKeyHeader,
    RateLimiter,
    SettingsDep,
    admin_key_valid,
    get_question_limiter,
)
from app.auth import sessions
from app.auth.crypto import TokenCipher
from app.core.config import Settings
from app.db.session import get_session

SESSION_COOKIE = "sils_session"


@dataclass
class Caller:
    user: sessions.SignedIn | None
    admin: bool


def sign_in_configured(settings: Settings) -> bool:
    return bool(
        settings.github_app_client_id
        and settings.github_app_client_secret
        and settings.token_encryption_key
    )


def optional_cipher(settings: SettingsDep) -> TokenCipher | None:
    key = settings.token_encryption_key
    return TokenCipher(key.get_secret_value()) if key else None


def get_caller(
    settings: SettingsDep,
    session: Annotated[Session, Depends(get_session)],
    cipher: Annotated[TokenCipher | None, Depends(optional_cipher)],
    x_admin_key: AdminKeyHeader = None,
    cookie: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> Caller:
    user = sessions.signed_in(session, cipher, cookie) if cookie and cipher else None
    if sign_in_configured(settings):
        # An unset admin key must not make everyone an admin once sign-in is on.
        admin = settings.admin_api_key is not None and admin_key_valid(
            settings, x_admin_key
        )
    else:
        admin = admin_key_valid(settings, x_admin_key)
    return Caller(user, admin)


CallerDep = Annotated[Caller, Depends(get_caller)]


def require_member(caller: CallerDep, settings: SettingsDep) -> Caller:
    """A signed-in user or the admin."""
    if caller.admin or caller.user is not None:
        return caller
    if sign_in_configured(settings):
        raise HTTPException(401, "Sign in with GitHub to do this")
    raise HTTPException(401, "Admin key required")


MemberDep = Annotated[Caller, Depends(require_member)]


def limit_questions(
    request: Request,
    settings: SettingsDep,
    caller: CallerDep,
    limiter: Annotated[RateLimiter, Depends(get_question_limiter)],
) -> None:
    """Cap how often one person can run search or the answer model.

    Signed-in users are counted by account and get a higher limit; everyone
    else is counted by IP address.
    """
    if caller.user is not None:
        client = f"user:{caller.user.user.id}"
        limit = settings.signed_in_questions_per_minute
    else:
        client = request.client.host if request.client else "unknown"
        limit = settings.questions_per_minute
    if limit <= 0:
        return
    wait = limiter.hit(client, limit)
    if wait is not None:
        seconds = max(1, round(wait))
        raise HTTPException(
            429,
            f"Too many questions. Try again in {seconds} seconds.",
            headers={"Retry-After": str(seconds)},
        )
