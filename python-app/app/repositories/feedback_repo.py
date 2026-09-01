"""Write path for user-submitted feedback -- stored verbatim, never summarized or altered."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.feedback import UserFeedback
from app.db.models.users import FoodUser


async def create(session: AsyncSession, user: FoodUser, source: str, message: str, now: datetime) -> UserFeedback:
    feedback = UserFeedback(user_id=user.id, source=source, message=message, created_at=now)
    session.add(feedback)
    await session.flush()
    return feedback
