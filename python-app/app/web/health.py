"""Health endpoints for the public and private management ASGI applications."""

from fastapi import APIRouter, FastAPI, Response
from sqlalchemy import text

from app.db.base import get_engine

public_router = APIRouter()
management_router = APIRouter()


@public_router.get("/health")
async def health() -> str:
    return "ok"


@management_router.get("/health/readiness")
async def readiness(response: Response) -> dict:
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "UP", "components": {"db": {"status": "UP"}}}
    except Exception as exc:  # noqa: BLE001 - readiness must report DOWN, not crash
        response.status_code = 503
        return {"status": "DOWN", "components": {"db": {"status": "DOWN", "error": str(exc)}}}


@management_router.get("/health/liveness")
async def liveness() -> dict:
    return {"status": "UP"}


def create_management_app() -> FastAPI:
    """Build the separate management app without exposing private checks publicly."""
    app = FastAPI(title="food-journal-bot-management")
    app.include_router(management_router)
    return app
