"""GET/DELETE /api/v1/memories -- user-visible companion memory management
(audit section 4.4). "User-controlled" means the app lists every durable fact
the agent saved and lets the user forget any of them; deletes are soft so the
history stays auditable."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.db.base import session_scope
from app.db.models.companion import CompanionMemory
from app.mobile.dependencies import MobilePrincipal, get_current_account
from app.mobile.rate_limit import message_rate_limit
from app.mobile.schemas import CompanionMemoryItem, MemoryListResponse
from app.repositories import companion_memory_repo

router = APIRouter(prefix="/api/v1/memories", tags=["mobile-memories"])

_rate_limited = [Depends(message_rate_limit)]


def _to_item(row: CompanionMemory) -> CompanionMemoryItem:
    return CompanionMemoryItem(
        id=row.id,
        kind=row.kind,
        text=row.text,
        source=row.source,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=MemoryListResponse, dependencies=_rate_limited)
async def list_memories(principal: MobilePrincipal = Depends(get_current_account)) -> MemoryListResponse:
    async with session_scope() as session:
        rows = await companion_memory_repo.list_active(session, principal.user)
        return MemoryListResponse(memories=[_to_item(row) for row in rows])


@router.delete("/{memory_id}", status_code=204, dependencies=_rate_limited)
async def delete_memory(memory_id: int, principal: MobilePrincipal = Depends(get_current_account)) -> None:
    async with session_scope() as session:
        row = await companion_memory_repo.find_active_by_id(session, principal.user, memory_id)
        if row is None:
            raise HTTPException(status_code=404, detail="memory not found")
        row.soft_delete(datetime.now(timezone.utc))
        await session.commit()
