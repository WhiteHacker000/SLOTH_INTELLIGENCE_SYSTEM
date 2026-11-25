import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.main import app
from app.models import WebhookDelivery

SECRET = "s3cret"
URL = "/api/v1/webhooks/github"


def headers(body: bytes, event: str = "ping", delivery: str = "d-1") -> dict[str, str]:
    digest = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return {
        "X-GitHub-Event": event,
        "X-GitHub-Delivery": delivery,
        "X-Hub-Signature-256": f"sha256={digest}",
        "Content-Type": "application/json",
    }


@pytest.fixture
def client(db_session: Session):
    db_session.commit = db_session.flush  # keep the test's rollback working
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, github_webhook_secret=SECRET
    )
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_ping_is_answered_and_recorded(client: TestClient, db_session: Session) -> None:
    body = json.dumps({"zen": "hi"}).encode()

    response = client.post(URL, content=body, headers=headers(body))

    assert response.json() == {"status": "pong"}
    assert db_session.get(WebhookDelivery, "d-1").event == "ping"


def test_a_redelivery_is_skipped(client: TestClient) -> None:
    body = b"{}"
    client.post(URL, content=body, headers=headers(body))

    again = client.post(URL, content=body, headers=headers(body))

    assert again.json() == {"status": "duplicate"}


def test_unknown_events_are_ignored(client: TestClient) -> None:
    body = b"{}"
    response = client.post(URL, content=body, headers=headers(body, event="star"))

    assert response.json() == {"status": "ignored"}


def test_a_bad_signature_is_refused(client: TestClient, db_session: Session) -> None:
    body = b"{}"
    forged = headers(b'{"other": 1}')

    response = client.post(URL, content=body, headers=forged)

    assert response.status_code == 401
    assert db_session.get(WebhookDelivery, "d-1") is None


def test_webhooks_are_off_without_a_secret(db_session: Session) -> None:
    app.dependency_overrides[get_session] = lambda: db_session
    try:
        response = TestClient(app).post(URL, content=b"{}", headers=headers(b"{}"))
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
