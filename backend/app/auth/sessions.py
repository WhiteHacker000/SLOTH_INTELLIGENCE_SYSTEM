import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.crypto import TokenCipher
from app.models import User, UserSession

# GitHub App user tokens expire after 8 hours. A session lasts as long as its
# token, so it never holds a token that no longer works.
DEFAULT_LIFETIME = timedelta(hours=8)


@dataclass
class SignedIn:
    user: User
    github_token: str


def save_user(
    session: Session, github_id: int, login: str, avatar_url: str | None
) -> User:
    """Create the user, or update their name and picture if they changed."""
    user = session.scalar(select(User).where(User.github_id == github_id))
    if user is None:
        user = User(github_id=github_id)
        session.add(user)
    user.login, user.avatar_url = login, avatar_url
    session.flush()
    return user


def start_session(
    session: Session,
    cipher: TokenCipher,
    user: User,
    github_token: str,
    lifetime: timedelta = DEFAULT_LIFETIME,
) -> str:
    """Store a new session and return the token for the cookie."""
    token = secrets.token_urlsafe(32)
    session.add(
        UserSession(
            token_hash=_hash(token),
            user_id=user.id,
            github_token=cipher.encrypt(github_token),
            expires_at=datetime.now(UTC) + lifetime,
        )
    )
    session.flush()
    return token


def signed_in(session: Session, cipher: TokenCipher, token: str) -> SignedIn | None:
    """Who a cookie token belongs to, or None if it is unknown or expired."""
    row = session.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(
            UserSession.token_hash == _hash(token),
            UserSession.expires_at > datetime.now(UTC),
        )
    ).first()
    if row is None:
        return None
    stored, user = row
    github_token = cipher.decrypt(stored.github_token)
    return SignedIn(user, github_token) if github_token else None


def end_session(session: Session, token: str) -> None:
    session.execute(delete(UserSession).where(UserSession.token_hash == _hash(token)))


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
