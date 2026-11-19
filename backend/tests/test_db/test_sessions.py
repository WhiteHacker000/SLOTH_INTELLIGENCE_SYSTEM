from datetime import timedelta

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import sessions
from app.auth.crypto import TokenCipher
from app.models import UserSession

CIPHER = TokenCipher(Fernet.generate_key().decode())


def sign_in(db: Session, lifetime: timedelta = sessions.DEFAULT_LIFETIME) -> str:
    user = sessions.save_user(db, github_id=7, login="octo", avatar_url=None)
    return sessions.start_session(db, CIPHER, user, "ghu_secret", lifetime)


def test_a_session_finds_its_user_and_token(db_session: Session) -> None:
    token = sign_in(db_session)

    found = sessions.signed_in(db_session, CIPHER, token)

    assert found is not None
    assert found.user.login == "octo"
    assert found.github_token == "ghu_secret"


def test_only_a_hash_and_ciphertext_are_stored(db_session: Session) -> None:
    token = sign_in(db_session)

    stored = db_session.scalars(select(UserSession)).one()

    assert token not in stored.token_hash
    assert "ghu_secret" not in stored.github_token


def test_unknown_expired_and_ended_sessions_are_rejected(db_session: Session) -> None:
    expired = sign_in(db_session, lifetime=timedelta(seconds=-1))
    ended = sign_in(db_session)
    sessions.end_session(db_session, ended)

    assert sessions.signed_in(db_session, CIPHER, "made-up") is None
    assert sessions.signed_in(db_session, CIPHER, expired) is None
    assert sessions.signed_in(db_session, CIPHER, ended) is None


def test_signing_in_again_updates_the_same_user(db_session: Session) -> None:
    first = sessions.save_user(db_session, github_id=7, login="octo", avatar_url=None)
    again = sessions.save_user(db_session, 7, "octo-renamed", "https://a.example/x")

    assert again.id == first.id
    assert again.login == "octo-renamed"
