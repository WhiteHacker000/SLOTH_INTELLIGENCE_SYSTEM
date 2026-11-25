import hashlib
import hmac
from collections.abc import Callable
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import WebhookDelivery

# Each event's handler returns a short status for the delivery log on GitHub.
Handler = Callable[[Session, dict[str, Any]], str]
HANDLERS: dict[str, Handler] = {
    "ping": lambda session, payload: "pong",
}


def signature_valid(secret: str, body: bytes, header: str | None) -> bool:
    """Checks GitHub's X-Hub-Signature-256 header against the raw body."""
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def first_delivery(session: Session, delivery_id: str, event: str) -> bool:
    """Records a delivery. False if it was seen before, as on a redelivery."""
    inserted = session.execute(
        insert(WebhookDelivery)
        .values(id=delivery_id, event=event)
        .on_conflict_do_nothing(index_elements=["id"])
        .returning(WebhookDelivery.id)
    ).first()
    return inserted is not None


def handle(session: Session, event: str, payload: dict[str, Any]) -> str:
    handler = HANDLERS.get(event)
    return handler(session, payload) if handler else "ignored"
