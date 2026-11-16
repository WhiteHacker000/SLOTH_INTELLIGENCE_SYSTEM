import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


def warm_up_models() -> None:
    """Load the embedding model and Gemma once, so the first real request is fast."""
    from app.embeddings.embedder import get_embedder
    from app.generation.llm import get_language_model

    try:
        get_embedder().embed_query("warm up")
        get_language_model().generate_json(
            "Reply with {}.", "warm up", {"type": "object"}
        )
        logger.info("Models are loaded")
    except Exception:
        logger.exception("Model warm-up failed; the first request will load them")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if get_settings().warm_up_models:
        # In a thread so the server starts answering straight away.
        threading.Thread(target=warm_up_models, daemon=True).start()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    application = FastAPI(
        title="Open-Source Decision Intelligence API",
        version="0.1.0",
        description="Foundation API for evidence-grounded project knowledge recovery.",
        lifespan=lifespan,
    )
    application.include_router(api_router, prefix="/api/v1")
    if settings.frontend_dist:
        # Mounted last so /api routes always win.
        application.mount(
            "/", StaticFiles(directory=settings.frontend_dist, html=True), name="ui"
        )
    return application


app = create_app()
