from datetime import date, datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def claim(session: AsyncSession, user_id: int, report_type: str, local_date: date) -> int:
    """INSERT ... ON CONFLICT DO NOTHING, matching ReportDeliveryRepository.claim():
    the idempotency gate that makes it safe for the once-a-minute scheduler tick
    to re-evaluate "is this due" repeatedly without double-sending."""
    result = await session.execute(
        text(
            "INSERT INTO report_deliveries (user_id, report_type, local_date, delivered_at) "
            "VALUES (:user_id, :report_type, :local_date, :delivered_at) "
            "ON CONFLICT (user_id, report_type, local_date) DO NOTHING"
        ),
        {"user_id": user_id, "report_type": report_type, "local_date": local_date, "delivered_at": datetime.now(timezone.utc)},
    )
    return result.rowcount
