from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class SignInUnavailable(RuntimeError):
    pass


class TokenCipher:
    """Encrypts GitHub tokens before they are stored."""

    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key)

    def encrypt(self, token: str) -> str:
        return self._fernet.encrypt(token.encode()).decode()

    def decrypt(self, stored: str) -> str | None:
        """None when the key has changed since the token was stored."""
        try:
            return self._fernet.decrypt(stored.encode()).decode()
        except InvalidToken:
            return None


def get_cipher() -> TokenCipher:
    key = get_settings().token_encryption_key
    if key is None:
        raise SignInUnavailable("Set TOKEN_ENCRYPTION_KEY to enable sign-in")
    return TokenCipher(key.get_secret_value())
