"""Slash commands and the onboarding stage machine.

Note on onboarding: continue_onboarding() is
confirmed (by direct investigation) to have NO call site in handle() -- in
production, once agent != null (always true when OPENAI_API_KEY is set), the
onboarding-stage transition actually happens through the agent calling the
update_settings tool during ordinary conversation, not through this
deterministic continuation path. That is replicated faithfully here: this
module exposes onboarding_prompt()/continue_onboarding() for completeness and
for the terminal/eval harness, but handle() below does not call
continue_onboarding for non-slash messages, matching confirmed production
behavior rather than an idealized one.
"""

from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.language import is_romanian
from app.db.models.users import FoodUser, UserSettings
from app.domain.agent_types import AgentContext
from app.repositories import feedback_repo, food_entry_repo, food_user_repo, telegram_access_repo

MIN_CALORIE_TARGET = 1200
MAX_CALORIE_TARGET = 5000
MAX_FEEDBACK_CHARS = 2000


class Agent(Protocol):
    async def run(self, session: AsyncSession, context: AgentContext) -> str: ...

    async def run_undo(self, session: AsyncSession, context: AgentContext) -> str: ...


def onboarding_prompt(settings: UserSettings, romanian: bool) -> str:
    if settings.onboarding_stage == "CALORIE_TARGET":
        return (
            "Care este ținta ta zilnică (1200–5000 kcal) sau scrie «skip»?"
            if romanian
            else "What is your daily calorie target (1200-5000), or say skip?"
        )
    return (
        "Bun venit. Trimite fusul IANA, de exemplu Europe/Bucharest."
        if romanian
        else "Welcome. Send your IANA timezone, for example Europe/Bucharest."
    )


def continue_onboarding(settings: UserSettings, message: str, romanian: bool) -> str | None:
    if settings.onboarding_completed:
        return None
    if settings.onboarding_stage == "TIMEZONE":
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(message.strip())
        except (ZoneInfoNotFoundError, ValueError, KeyError):
            return (
                "Trimite un fus IANA valid, de exemplu Europe/Bucharest."
                if romanian
                else "Please send a valid IANA timezone, for example Europe/Bucharest."
            )
        settings.timezone = message.strip()
        settings.require_calorie_target()
        return (
            "Fus salvat. Care este ținta ta zilnică (1200–5000 kcal) sau scrie «skip»?"
            if romanian
            else "Timezone saved. What is your daily calorie target (1200-5000), or say skip?"
        )
    # stage == "CALORIE_TARGET"
    if message.strip().lower() == "skip":
        settings.skip_calorie_target()
        return (
            "Configurare terminată. Poți seta ținta mai târziu din /settings."
            if romanian
            else "Setup complete. You can set a calorie target later in /settings."
        )
    try:
        target = int(message.strip())
    except ValueError:
        return (
            "Trimite o țintă între 1200 și 5000 kcal sau «skip»."
            if romanian
            else "Send a daily calorie target between 1200 and 5000, or say skip."
        )
    if target < MIN_CALORIE_TARGET or target > MAX_CALORIE_TARGET:
        return (
            "Ținta trebuie să fie între 1200 și 5000 kcal sau scrie «skip»."
            if romanian
            else "Your daily target must be between 1200 and 5000 kcal, or say skip."
        )
    settings.calorie_target = target
    settings.skip_calorie_target()
    return (
        f"Configurare terminată. Ținta ta este {target} kcal."
        if romanian
        else f"Setup complete. Your daily target is {target} kcal."
    )


async def _today_text(session, user: FoodUser, settings: UserSettings, romanian: bool) -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    zone = ZoneInfo(settings.timezone)
    today = datetime.now(zone).date()
    calories, _count = await food_entry_repo.today_totals(session, user, settings.timezone, today)
    target = settings.calorie_target
    if romanian:
        return f"Total azi: {calories} kcal" + ("." if target is None else f" din {target} kcal.")
    return f"Today: {calories} kcal" + ("." if target is None else f" of {target} kcal.")


def _command_token(raw: str) -> str:
    """Extract the leading slash-command token (e.g. '/undo' from '/undo foo'),
    lower-cased and stripped. Used by both handle()'s pre-dispatch and command()'s
    table lookup so the two paths parse the command identically."""
    return raw.strip().lower().split(maxsplit=1)[0]


async def command(session, user: FoodUser, settings: UserSettings, raw: str, romanian: bool, is_admin: bool = False) -> str:
    cmd = _command_token(raw)
    if cmd == "/start":
        if settings.onboarding_completed:
            return (
                "Bine ai revenit. Exemple: «165 g crispy, 229 kcal/100 g», «cate calorii azi?», «arată-mi mesele de ieri»."
                if romanian
                else "Welcome back. Examples: “165 g crispy, 229 kcal/100 g”, “how many calories today?”, “show yesterday's meals”."
            )
        return onboarding_prompt(settings, romanian)
    if cmd == "/help":
        admin_commands = "\n\nAdmin commands: /adduser TELEGRAM_ID, /removeuser TELEGRAM_ID" if is_admin else ""
        return (
            "Pot nota mai multe mese dintr-un singur mesaj, inclusiv pe zile trecute; pot estima nutriția, muta, corecta "
            "sau șterge direct și poți folosi Undo timp de 10 minute.\n\nComenzi: /start, /help, /today, /report, "
            "/settings, /cancel, /privacy, /undo, /feedback" + admin_commands
            if romanian
            else "I can log several meals from one message, including past dates; estimate nutrition; and move, edit, "
            "or delete entries immediately with a 10-minute Undo window.\n\nCommands: /start, /help, /today, /report, "
            "/settings, /cancel, /privacy, /undo, /feedback" + admin_commands
        )
    if cmd in ("/today", "/report"):
        return await _today_text(session, user, settings, romanian)
    if cmd == "/settings":
        target_text = ("nesetată" if romanian else "not set") if settings.calorie_target is None else f"{settings.calorie_target} kcal"
        reports_text = ("pornite" if settings.reports_enabled else "oprite") if romanian else ("on" if settings.reports_enabled else "off")
        if romanian:
            return f"Setări: fus {settings.timezone}, țintă {target_text}, rapoarte {reports_text}. Poți modifica aceste setări conversațional."
        return f"Settings: timezone {settings.timezone}, target {target_text}, reports {reports_text}. You can change these conversationally."
    if cmd == "/cancel":
        return "Am anulat draftul conversațional curent." if romanian else "I cancelled the current conversational draft."
    if cmd == "/feedback":
        from datetime import UTC, datetime

        text = raw.strip()[len(cmd):].strip()
        if not text:
            return (
                "Scrie feedback-ul după comandă, de exemplu: /feedback ar fi util un grafic săptămânal."
                if romanian
                else "Add your feedback after the command, e.g. /feedback a weekly chart would help."
            )
        await feedback_repo.create(session, user, "command", text[:MAX_FEEDBACK_CHARS], datetime.now(UTC))
        return "Mulțumesc, am notat feedback-ul." if romanian else "Thanks, I've recorded your feedback."
    if cmd == "/privacy":
        return (
            "Păstrez intrările jurnalului, cel mult 10 mesaje recente, change-set-uri Undo temporare și feedback-ul "
            "trimis prin /feedback sau prin conversație. Fișierele originale nu sunt păstrate."
            if romanian
            else "I retain journal entries, at most 10 recent messages, temporary Undo change sets, and any "
            "feedback sent via /feedback or in conversation. Original media files are not retained."
        )
    return "Comandă necunoscută. Folosește /help." if romanian else "Unknown command. Use /help."


def unavailable(romanian: bool) -> str:
    return (
        "Nu pot procesa cererea acum. Încearcă din nou sau trimite detaliile mesei în text."
        if romanian
        else "I cannot process that right now. Please try again or send the meal details as text."
    )


class JournalApplicationService:
    def __init__(self, default_timezone: str, agent: Agent | None = None) -> None:
        self.default_timezone = default_timezone
        self._agent = agent

    async def handle(
        self,
        session,
        user: FoodUser,
        chat_id: str,
        message: str,
        *,
        media_kind: str | None = None,
        media_text: str | None = None,
        media_caption: str | None = None,
    ) -> str:
        settings = await food_user_repo.get_settings(session, user.id)

        if message.startswith("/"):
            romanian = settings.preferred_language == "ro"
            cmd = _command_token(message)
            if cmd == "/undo":
                # Deliberately bypasses command()'s deterministic-only dispatch:
                # undo reverses a journal mutation, which lives behind the same
                # undo_last_change tool that natural-language undo ("undo that",
                # "anuleaza") already calls through the agent.
                if self._agent is None:
                    return unavailable(romanian)
                context = AgentContext(user=user, chat_id=chat_id, romanian=romanian, message=message)
                return await self._agent.run_undo(session, context)
            is_private_admin = (
                user.telegram_user_id is not None
                and chat_id == str(user.telegram_user_id)
                and await telegram_access_repo.is_admin(session, user.telegram_user_id)
            )
            return await command(session, user, settings, message, romanian, is_private_admin)

        romanian = is_romanian(message)
        settings.set_preferred_language("ro" if romanian else "en")

        if self._agent is not None:
            context = AgentContext(
                user=user,
                chat_id=chat_id,
                romanian=romanian,
                message=message,
                media_kind=media_kind,
                media_text=media_text,
                media_caption=media_caption,
            )
            return await self._agent.run(session, context)
        return unavailable(romanian)
