import hashlib
import hmac

from app.github_app.webhooks import signature_valid

BODY = b'{"zen": "Keep it logically awesome."}'


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_accepts_githubs_signature() -> None:
    assert signature_valid("s3cret", BODY, sign("s3cret", BODY))


def test_rejects_a_wrong_secret_or_changed_body() -> None:
    assert not signature_valid("s3cret", BODY, sign("other", BODY))
    assert not signature_valid("s3cret", BODY + b" ", sign("s3cret", BODY))


def test_rejects_a_missing_or_old_style_header() -> None:
    assert not signature_valid("s3cret", BODY, None)
    assert not signature_valid("s3cret", BODY, "sha1=abc")
