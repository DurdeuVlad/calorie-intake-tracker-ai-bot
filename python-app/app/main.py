from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.base import dispose_engine, get_engine
from app.telegram_bot.webhook_router import router as telegram_webhook_router
from app.web.health import public_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    get_engine()  # eagerly create the pool so a bad DATABASE_URL fails fast at startup
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(title="food-journal-bot", lifespan=lifespan)
    app.include_router(public_router)
    app.include_router(telegram_webhook_router)
    return app


app = create_app()
