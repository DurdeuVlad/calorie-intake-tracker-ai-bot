import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import telegram_access_repo

_COMMAND = re.compile(r"^/(add[_-]?user|remove[_-]?user|add|remove)(?:@[^\s]+)?\s+([0-9]+)\s*$", re.IGNORECASE)


def parse_command(text: str | None) -> tuple[str, int] | None:
    if not text:
        return None
    match = _COMMAND.match(text.strip())
    return (match.group(1).lower(), int(match.group(2))) if match else None


async def handle_command(session: AsyncSession, text: str, actor_id: int, private_chat: bool) -> str | None:
    parsed = parse_command(text)
    if parsed is None:
        return None
    if not private_chat:
        return "Admin commands are available only in a private chat."
    if not await telegram_access_repo.is_admin(session, actor_id):
        return "You are not authorized to manage users."
    command, target_id = parsed
    if target_id == actor_id:
        return "You cannot change your own administrator access."
    if command in {"add", "adduser", "add_user", "add-user"}:
        await telegram_access_repo.grant_user(session, target_id, actor_id)
        return "User access granted."
    if not await telegram_access_repo.revoke_user(session, target_id):
        return "That user is not a removable regular user."
    return "User access removed."
