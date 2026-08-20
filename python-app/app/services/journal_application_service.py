"""Slash commands + onboarding stage machine, ported from JournalApplicationService.java.

Note on onboarding: continueOnboarding() exists in the Java source but is
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
from app.repositories import food_entry_repo, food_user_repo

MIN_CALORIE_TARGET = 1200
MAX_CALORIE_TARGET = 5000


class Agent(Protocol):
    async def run(self, session: AsyncSession, context: AgentContext) -> str: ...


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


async def command(session, user: FoodUser, settings: UserSettings, raw: str, romanian: bool) -> str:
    cmd = raw.strip().lower().split(maxsplit=1)[0]
    if cmd == "/start":
        if settings.onboarding_completed:
            return (
                "Bine ai revenit. Exemple: «165 g crispy, 229 kcal/100 g», «cate calorii azi?», «arată-mi mesele de ieri»."
                if romanian
                else "Welcome back. Examples: “165 g crispy, 229 kcal/100 g”, “how many calories today?”, “show yesterday's meals”."
            )
        return onboarding_prompt(settings, romanian)
    if cmd == "/help":
        return (
            "Pot nota mai multe mese dintr-un singur mesaj, inclusiv pe zile trecute; pot estima nutriția, muta, corecta "
            "sau șterge direct și poți folosi Undo timp de 10 minute.\n\nComenzi: /start, /help, /today, /report, "
            "/settings, /cancel, /privacy"
            if romanian
            else "I can log several meals from one message, including past dates; estimate nutrition; and move, edit, "
            "or delete entries immediately with a 10-minute Undo window.\n\nCommands: /start, /help, /today, /report, "
            "/settings, /cancel, /privacy"
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
    if cmd == "/privacy":
        return (
            "Păstrez intrările jurnalului, cel mult 10 mesaje recente și change-set-uri Undo temporare. "
            "Fișierele originale nu sunt păstrate."
            if romanian
            else "I retain journal entries, at most 10 recent messages, and temporary Undo change sets. "
            "Original media files are not retained."
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

    async def handle(self, session, user: FoodUser, chat_id: str, message: str) -> str:
        settings = await food_user_repo.get_settings(session, user.id)

        if message.startswith("/"):
            romanian = settings.preferred_language == "ro"
            return await command(session, user, settings, message, romanian)

        romanian = is_romanian(message)
        settings.set_preferred_language("ro" if romanian else "en")

        if self._agent is not None:
            context = AgentContext(user=user, chat_id=chat_id, romanian=romanian, message=message)
            return await self._agent.run(session, context)
        return unavailable(romanian)
