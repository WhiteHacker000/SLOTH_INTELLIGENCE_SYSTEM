from fastapi import FastAPI

from app.api.router import api_router

app = FastAPI(
    title="Open-Source Decision Intelligence API",
    version="0.1.0",
    description="Foundation API for evidence-grounded project knowledge recovery.",
)
app.include_router(api_router, prefix="/api/v1")
