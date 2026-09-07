"""Slash commands and onboarding fallback.

v2.0: onboarding is driven by the agent, not deterministic if-else stage
branches. When the agent is available, /start for an incomplete user is
routed to the agent, which greets the user, explains what the bot does
(text/voice/photo logging, totals, undo), and collects name, timezone,
and calorie target naturally via update_settings. The functions below
are minimal fallbacks for when no agent is configured.
"""

from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.users import FoodUser, UserSettings
from app.domain.agent_types import AgentContext
from app.repositories import (
    feedback_repo,
    food_entry_repo,
    food_user_repo,
    telegram_access_repo,
)


def onboarding_fallback(romanian: bool) -> str:
    """Minimal static greeting used only when no agent is configured.
    The agent normally drives onboarding with a richer, conversational prompt."""
    return (
        "Salut! Sunt botul tău de jurnal alimentar. Trimite-mi ce mănânci prin "
        "text, notă vocală sau poză și notez caloriile. Cum te cheamă?"
        if romanian
        else "Hi! I'm your food journal bot. Send me what you eat by text, voice, "
        "or photo and I'll log the calories. What's your name?"
    )


class Agent(Protocol):
    async def run(self, session: AsyncSession, context: AgentContext) -> str: ...

    async def run_undo(self, session: AsyncSession, context: AgentContext) -> str: ...


async def _today_text(
    session,
    user: FoodUser,
    settings: UserSettings,
    romanian: bool,
    reference_time: datetime | None = None,
) -> str:
    from zoneinfo import ZoneInfo

    zone = ZoneInfo(settings.timezone)
    today = food_entry_repo.local_tracking_date(reference_time or datetime.now(zone), zone, settings.day_boundary_hour)
    calories, _count = await food_entry_repo.today_totals(session, user, settings.timezone, today, settings.day_boundary_hour)
    target = settings.calorie_target
    if target is None:
        return f"Total azi: {calories} kcal." if romanian else f"Today: {calories} kcal."
    if settings.target_mode == "min":
        if romanian:
            return f"Total azi: {calories} kcal, minim {target} kcal."
        return f"Today: {calories} kcal, minimum {target} kcal."
    if romanian:
        return f"Total azi: {calories} kcal din {target} kcal."
    return f"Today: {calories} kcal of {target} kcal."


def _command_token(raw: str) -> str:
    """Extract the leading slash-command token (e.g. '/undo' from '/undo foo'),
    lower-cased and stripped. Used by both handle()'s pre-dispatch and command()'s
    table lookup so the two paths parse the command identically."""
    return raw.strip().lower().split(maxsplit=1)[0]


async def command(
    session,
    user: FoodUser,
    settings: UserSettings,
    raw: str,
    romanian: bool,
    is_admin: bool = False,
    reference_time: datetime | None = None,
) -> str:
    cmd = _command_token(raw)
    if cmd == "/start":
        if settings.onboarding_completed:
            return (
                "Bine ai revenit. Exemple: «165 g crispy, 229 kcal/100 g», «cate calorii azi?», «arată-mi mesele de ieri»."
                if romanian
                else "Welcome back. Examples: “165 g crispy, 229 kcal/100 g”, “how many calories today?”, “show yesterday's meals”."
            )
        return onboarding_fallback(romanian)
    if cmd == "/help":
        admin_commands = "\n\nAdmin commands: /adduser TELEGRAM_ID, /removeuser TELEGRAM_ID" if is_admin else ""
        return (
            "Pot nota mai multe mese dintr-un singur mesaj, inclusiv pe zile trecute; pot estima nutriția, muta, corecta "
            "sau șterge direct și poți folosi Undo timp de 10 minute.\n\nComenzi: /start, /help, /today, /report, "
            "/settings, /cancel, /privacy, /undo, /feedback, /bug" + admin_commands
            if romanian
            else "I can log several meals from one message, including past dates; estimate nutrition; and move, edit, "
            "or delete entries immediately with a 10-minute Undo window.\n\nCommands: /start, /help, /today, /report, "
            "/settings, /cancel, /privacy, /undo, /feedback, /bug" + admin_commands
        )
    if cmd in ("/today", "/report"):
        return await _today_text(session, user, settings, romanian, reference_time)
    if cmd == "/settings":
        target_text = ("nesetată" if romanian else "not set") if settings.calorie_target is None else f"{settings.calorie_target} kcal"
        reports_text = ("pornite" if settings.reports_enabled else "oprite") if romanian else ("on" if settings.reports_enabled else "off")
        boundary_text = "miezul nopții" if settings.day_boundary_hour == 0 else f"ora {settings.day_boundary_hour}:00"
        reminder_text = ("pornit" if settings.day_boundary_reminder_enabled else "oprit") if romanian else ("on" if settings.day_boundary_reminder_enabled else "off")
        mode_text_ro = "minim" if settings.target_mode == "min" else "maxim"
        mode_text_en = "minimum" if settings.target_mode == "min" else "maximum"
        budget_text = ("pornite" if settings.budget_alerts_enabled else "oprite") if romanian else ("on" if settings.budget_alerts_enabled else "off")
        nudge_text = ("pornit" if settings.tracking_nudge_enabled else "oprit") if romanian else ("on" if settings.tracking_nudge_enabled else "off")
        if romanian:
            return (
                f"Setări: fus {settings.timezone}, țintă {target_text} ({mode_text_ro}), rapoarte {reports_text}, "
                f"ziua începe la {boundary_text}, memento început zi {reminder_text}, alerte buget {budget_text}, "
                f"memento urmărire {nudge_text}. Poți modifica aceste setări conversațional."
            )
        boundary_text_en = "midnight" if settings.day_boundary_hour == 0 else f"{settings.day_boundary_hour}:00"
        return (
            f"Settings: timezone {settings.timezone}, target {target_text} ({mode_text_en}), reports {reports_text}, "
            f"day starts at {boundary_text_en}, day-boundary reminder {reminder_text}, budget alerts {budget_text}, "
            f"tracking nudge {nudge_text}. You can change these conversationally."
        )
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
        await feedback_repo.create(session, user, "command", text, datetime.now(UTC))
        return "Mulțumesc, am notat feedback-ul." if romanian else "Thanks, I've recorded your feedback."
    if cmd == "/privacy":
        return (
            "Păstrez intrările jurnalului, cel mult 10 mesaje recente, change-set-uri Undo temporare și feedback-ul "
            "trimis prin /feedback sau prin conversație. Fișierele originale nu sunt păstrate."
            if romanian
            else "I retain journal entries, at most 10 recent messages, temporary Undo change sets, and any "
            "feedback sent via /feedback or in conversation. Original media files are not retained."
        )
    if cmd in ("/bug", "/feedback"):
        rest = raw.strip()[len(cmd):].strip()
        if not rest:
            return (
                "Folosește /bug <descriere> pentru a raporta o problemă. Ex: /bug a logat pizza de două ori."
                if romanian
                else "Use /bug <description> to report a problem. E.g. /bug it logged pizza twice."
            )
        await feedback_repo.save(session, user, kind="bug", message=rest)
        return (
            "Am salvat raportul tău. Mulțumesc!"
            if romanian
            else "Saved your report. Thank you!"
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
        started_at: datetime | None = None,
    ) -> str:
        settings = await food_user_repo.get_settings(session, user.id)
        request_time = started_at or datetime.now(UTC)

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
                context = AgentContext(user=user, chat_id=chat_id, message=message, started_at=request_time)
                return await self._agent.run_undo(session, context)
            if cmd == "/start" and not settings.onboarding_completed and self._agent is not None:
                # v2.0: onboarding is driven by the agent, not deterministic if-else
                # stage branches. The system prompt tells the model to greet the
                # user, explain what the bot does (text/voice/photo), and collect
                # name, timezone, and calorie target naturally via update_settings.
                context = AgentContext(
                    user=user,
                    chat_id=chat_id,
                    message=message,
                    media_kind=media_kind,
                    media_text=media_text,
                    media_caption=media_caption,
                    started_at=request_time,
                )
                return await self._agent.run(session, context)
            is_private_admin = (
                user.telegram_user_id is not None
                and chat_id == str(user.telegram_user_id)
                and await telegram_access_repo.is_admin(session, user.telegram_user_id)
            )
            return await command(
                session,
                user,
                settings,
                message,
                romanian,
                is_private_admin,
                request_time,
            )

        # v2.0: the model decides the reply language. is_romanian() is no longer
        # called in the agent path. preferred_language is kept as a hint for
        # slash-command dispatch only, derived from the user's last slash-command
        # language or explicit setting.

        if self._agent is not None:
            context = AgentContext(
                user=user,
                chat_id=chat_id,
                message=message,
                media_kind=media_kind,
                media_text=media_text,
                media_caption=media_caption,
                started_at=request_time,
            )
            return await self._agent.run(session, context)
        return unavailable(settings.preferred_language == "ro")
