import pytest
from cryptography.fernet import Fernet

from app.auth import crypto
from app.auth.crypto import SignInUnavailable, TokenCipher
from app.core.config import Settings


def test_tokens_round_trip_and_are_not_stored_in_clear() -> None:
    cipher = TokenCipher(Fernet.generate_key().decode())

    stored = cipher.encrypt("ghu_secret")

    assert "ghu_secret" not in stored
    assert cipher.decrypt(stored) == "ghu_secret"


def test_a_changed_key_cannot_read_old_tokens() -> None:
    stored = TokenCipher(Fernet.generate_key().decode()).encrypt("ghu_secret")

    assert TokenCipher(Fernet.generate_key().decode()).decrypt(stored) is None


def test_sign_in_needs_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crypto, "get_settings", lambda: Settings(_env_file=None))

    with pytest.raises(SignInUnavailable):
        crypto.get_cipher()
