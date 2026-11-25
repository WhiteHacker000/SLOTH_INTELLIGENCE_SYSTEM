import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.github_app import webhooks

router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/github")
async def github_webhook(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    event: Annotated[str, Header(alias="X-GitHub-Event")],
    delivery_id: Annotated[str, Header(alias="X-GitHub-Delivery", max_length=64)],
    signature: Annotated[str | None, Header(alias="X-Hub-Signature-256")] = None,
) -> dict[str, str]:
    """Receives events from the SilS GitHub App."""
    if settings.github_webhook_secret is None:
        raise HTTPException(503, "Webhooks are not set up on this server")
    body = await request.body()
    secret = settings.github_webhook_secret.get_secret_value()
    if not webhooks.signature_valid(secret, body, signature):
        raise HTTPException(401, "Invalid signature")
    try:
        payload = json.loads(body)
    except ValueError:
        raise HTTPException(400, "Body is not JSON") from None
    if not webhooks.first_delivery(session, delivery_id, event):
        return {"status": "duplicate"}
    status = webhooks.handle(session, event, payload)
    session.commit()
    return {"status": status}
